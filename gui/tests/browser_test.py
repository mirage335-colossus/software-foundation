#!/usr/bin/env python3
"""Optional actual-browser qualification of copied hosted or Wasm assets.

No third-party Python package. Runs hosted and Wasm modes against the same DOM,
checks accessible labels, editing and geometry, and saves comparable captures.
"""
import argparse
import base64
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import socket
import signal
import subprocess
import tempfile
import threading
import time
import urllib.request
import urllib.error


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
    if os.name == 'posix':
        try: os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError: pass


class Browser:
    def __init__(self, executable, directory):
        self.profile=directory/'profile';self.profile.mkdir()
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
        (self.profile/'user.js').write_text(f'user_pref("marionette.port", {port});\nuser_pref("browser.shell.checkDefaultBrowser", false);\n')
        self.log=(directory/'firefox.log').open('w')
        self.process=subprocess.Popen([executable,'--headless','--no-remote','--marionette','--profile',str(self.profile)],
            stdout=self.log,stderr=self.log,env=dict(os.environ,MOZ_HEADLESS='1'),start_new_session=os.name=='posix')
        self.socket=None;self.sequence=0
        try:
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                try:self.socket=socket.create_connection(('127.0.0.1',port),timeout=1);break
                except OSError:
                    if self.process.poll() is not None:raise RuntimeError('Firefox exited during startup')
                    time.sleep(.1)
            if self.socket is None:raise TimeoutError('Firefox automation startup timeout')
            self.socket.settimeout(15);self.receive()
            self.capabilities=self.command('WebDriver:NewSession',{'capabilities':{}})['capabilities']
            self.command('WebDriver:SetWindowRect',{'width':800,'height':760})
        except Exception:self.close();raise

    def receive(self):
        prefix=b''
        while not prefix.endswith(b':'):
            byte=self.socket.recv(1)
            if not byte:raise RuntimeError('Browser connection closed')
            prefix+=byte
            if len(prefix)>16:raise ValueError('Browser packet header too large')
        length=int(prefix[:-1]);data=bytearray()
        if length>32*1024*1024:raise ValueError('Browser packet too large')
        while len(data)<length:
            chunk=self.socket.recv(length-len(data))
            if not chunk:raise RuntimeError('Browser connection closed')
            data.extend(chunk)
        return json.loads(data)

    def command(self,name,args):
        self.sequence+=1;payload=json.dumps([0,self.sequence,name,args]).encode()
        self.socket.sendall(str(len(payload)).encode()+b':'+payload)
        response=self.receive()
        if response[1]!=self.sequence or response[2]:raise RuntimeError(str(response))
        return response[3]

    def script(self,source):
        return self.command('WebDriver:ExecuteScript',{'script':source,'args':[],'newSandbox':True,'sandbox':None})['value']

    def wait(self,source):
        deadline=time.monotonic()+15
        while time.monotonic()<deadline:
            if self.script(source):return
            time.sleep(.05)
        raise TimeoutError('Browser condition timed out: '+source)

    def close(self):
        if self.socket:self.socket.close()
        stop_process(self.process)
        self.log.close()


class ChromiumBrowser(Browser):
    """The same DOM fixture through the local W3C WebDriver HTTP interface."""
    def __init__(self, executable, driver, directory, arguments):
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
        self.base='http://127.0.0.1:'+str(port);self.session=None
        self.log=(directory/'chromedriver.log').open('w')
        self.process=subprocess.Popen([driver,'--port='+str(port),'--allowed-ips=127.0.0.1'],
            stdout=self.log,stderr=self.log,start_new_session=os.name=='posix')
        try:
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                try:
                    if self.request('GET','/status')['ready']:break
                except (OSError,KeyError):pass
                if self.process.poll() is not None:raise RuntimeError('Browser driver exited during startup')
                time.sleep(.1)
            else:raise TimeoutError('Browser driver startup timeout')
            result=self.request('POST','/session',{'capabilities':{'alwaysMatch':{
                'browserName':'chrome','goog:chromeOptions':{'binary':str(Path(executable).resolve()),
                'args':['--headless=new','--disable-dev-shm-usage','--no-first-run',
                        '--user-data-dir='+str(directory/'profile'),*arguments]}}}})
            self.session=result['sessionId']
            self.capabilities=result['capabilities']
            self.request('POST',self.path('/window/rect'),{'width':800,'height':760})
        except Exception:self.close();raise

    def path(self,suffix):return '/session/'+self.session+suffix

    def request(self,method,path,data=None):
        request=urllib.request.Request(self.base+path,data=None if data is None else json.dumps(data).encode(),
            headers={'Content-Type':'application/json'},method=method)
        try:
            with urllib.request.urlopen(request,timeout=20) as response:
                raw=response.read(32*1024*1024+1)
                if len(raw)>32*1024*1024:raise ValueError('Browser response exceeds limit')
                result=json.loads(raw)['value']
        except urllib.error.HTTPError as error:
            raise RuntimeError('Browser driver rejected request: '+error.read(8192).decode(errors='replace')) from error
        if isinstance(result,dict) and 'error' in result:raise RuntimeError(str(result))
        return result

    def command(self,name,args):
        if name=='WebDriver:Navigate':return self.request('POST',self.path('/url'),{'url':args['url']})
        if name=='WebDriver:ExecuteScript':return {'value':self.request('POST',self.path('/execute/sync'),
            {'script':args['script'],'args':args['args']})}
        if name=='WebDriver:TakeScreenshot':return {'value':self.request('GET',self.path('/screenshot'))}
        raise ValueError('Unsupported browser command')

    def close(self):
        try:
            if self.session:self.request('DELETE',self.path(''))
        finally:stop_process(self.process);self.log.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firefox',default='firefox');parser.add_argument('--server',type=Path,required=True)
    parser.add_argument('--browser',choices=('firefox','chromium'),default='firefox')
    parser.add_argument('--browser-executable',help='Explicit Chromium executable for its matching driver')
    parser.add_argument('--driver',default='chromedriver')
    parser.add_argument('--browser-argument',action='append',default=[])
    parser.add_argument('--mode',choices=('hosted','wasm','both'),default='both')
    parser.add_argument('--executable',type=Path);parser.add_argument('--wasm-dir',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    modes=('hosted','wasm') if args.mode=='both' else (args.mode,)
    if 'hosted' in modes and not args.executable:parser.error('Hosted qualification requires --executable')
    if 'wasm' in modes and not args.wasm_dir:parser.error('Wasm qualification requires --wasm-dir')
    if args.browser=='chromium' and not args.browser_executable:parser.error('Chromium requires --browser-executable')
    args.output.mkdir(parents=True,exist_ok=False)
    inputs=[Path(__file__).resolve(),args.server,
            *(args.server.parent/name for name in ('host.py','renderer.mjs','boot.mjs','style.css','index.html'))]
    if 'hosted' in modes:inputs.append(args.executable)
    if 'wasm' in modes:inputs.extend(args.wasm_dir/name for name in ('gui_web_wasm.js','gui_web_wasm.wasm'))
    identify=lambda:{str(path.resolve()):hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    expected_inputs=identify()
    spec=importlib.util.spec_from_file_location('server',args.server);server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)
    host=server.boundary.Host(('127.0.0.1',0),args.executable,args.wasm_dir)
    thread=threading.Thread(target=host.serve_forever);thread.start()
    try:
        with tempfile.TemporaryDirectory(prefix='browser-',dir=args.output) as directory:
            browser=(Browser(args.firefox,Path(directory)) if args.browser=='firefox' else
                ChromiumBrowser(args.browser_executable,args.driver,Path(directory),args.browser_argument))
            try:
                layouts=[]
                for mode in modes:
                    browser.command('WebDriver:Navigate',{'url':'http://'+host.authority+'/?mode='+mode})
                    browser.wait('return Boolean(document.querySelector("input.editor"));')
                    # Fixed viewport makes geometry directly comparable across transports.
                    browser.script('document.querySelector("#viewport").style.width="800px";document.querySelector("#viewport").style.height="640px";')
                    browser.wait('return document.querySelector("input.editor").getBoundingClientRect().width===752;')
                    if browser.script('return document.querySelector("input.editor").getAttribute("aria-label");')!='New entry':
                        raise RuntimeError('Accessible editor name differs')
                    browser.script('const e=document.querySelector("input.editor");e.value="Browser entry";e.dispatchEvent(new InputEvent("input",{bubbles:true}));')
                    browser.wait('return !Array.from(document.querySelectorAll("button")).find(x=>x.textContent==="Add entry").disabled;')
                    browser.script('Array.from(document.querySelectorAll("button")).find(x=>x.textContent==="Add entry").click();')
                    browser.wait('return Boolean(document.querySelector("[role=option][aria-label=\\"Browser entry\\"]"));')
                    if browser.script('return document.querySelector("input.editor").value;')!='':
                        raise RuntimeError('Submitted editor was not cleared')
                    layouts.append(browser.script('return Array.from(document.querySelectorAll(".widget")).map(e=>({key:e.dataset.key,box:[e.offsetLeft,e.offsetTop,e.offsetWidth,e.offsetHeight]}));'))
                    result=browser.command('WebDriver:TakeScreenshot',{'id':None,'full':False,'scroll':False})
                    (args.output/(mode+'.png')).write_bytes(base64.b64decode(result['value'],validate=True))
                    browser.script('const m=Array.from(document.querySelectorAll("select")).find(x=>x.getAttribute("aria-label")==="Actions");m.value="heading";m.dispatchEvent(new Event("change",{bubbles:true}));')
                    browser.wait('return Boolean(document.querySelector("dialog[open]"));')
                    browser.script('Array.from(document.querySelectorAll("dialog button")).find(x=>x.textContent==="Cancel").click();')
                    browser.wait('return !document.querySelector("dialog[open]");')
                if len(layouts)==2 and layouts[0]!=layouts[1]:raise RuntimeError('Hosted and Wasm DOM geometry differ')
                (args.output/'geometry.json').write_text(json.dumps(layouts[0],indent=2)+'\n')
                browser_version=browser.capabilities['browserVersion']
            finally:browser.close()
    finally:
        host.shutdown();thread.join(timeout=5);host.server_close()
    if thread.is_alive():raise RuntimeError('Browser host thread did not stop')
    if identify()!=expected_inputs:raise RuntimeError('Browser qualification inputs changed while running')
    receipt={'schema_version':1,'status':'passed','engine':args.browser,'browser_version':browser_version,
             'mode':args.mode,'checks':['editing','accessible-names','shared-geometry','prompt-cancel','capture','cleanup'],
             'inputs':expected_inputs,
             'browser_arguments':args.browser_argument}
    temporary=args.output/'qualification.tmp'
    with temporary.open('x') as stream:
        stream.write(json.dumps(receipt,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
    temporary.replace(args.output/'qualification.json')
    print('Actual '+args.browser+' '+args.mode+' editing, accessibility labels, geometry, prompt cancellation and captures passed')


if __name__=='__main__':main()
