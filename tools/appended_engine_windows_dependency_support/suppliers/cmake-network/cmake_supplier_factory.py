"""Pure fixed four-supplier Windows static CMake declarations.

Reviewed source-only overlays. No supplier tree/body I/O, process, archive, SDK,
program, network or runtime qualification operation occurs in this module.
"""
import copy
import _foundation_windows_supplier_factory_contract_v1 as _factory

SOURCES = {'curl': {'archive': 'curl.tar.xz', 'bytes': 2797000, 'format': 'tar-xz', 'sha256': '955f6e729ad6b3566260e8fef68620e76ba3c31acf0a18524416a185acf77992', 'strip_prefix': 'curl-8.17.0', 'version': '8.17.0'}, 'harfbuzz': {'archive': 'harfbuzz.tar.xz', 'bytes': 17895360, 'format': 'tar-xz', 'sha256': 'a41b272ceeb920c57263ec851604542d9ec85ee3030506d94662067c7b6ab89e', 'strip_prefix': 'harfbuzz-9.0.0', 'version': '9.0.0'}, 'nghttp2': {'archive': 'nghttp2.tar.xz', 'bytes': 1676124, 'format': 'tar-xz', 'sha256': '88bb94c9e4fd1c499967f83dece36a78122af7d5fb40da2019c56b9ccc6eb9dd', 'strip_prefix': 'nghttp2-1.64.0', 'version': '1.64.0'}, 'xml2': {'archive': 'libxml2.tar.xz', 'bytes': 2643456, 'format': 'tar-xz', 'sha256': '59912db536ab56a3996489ea0299768c7bcffe57169f0235e7f962a91f483590', 'strip_prefix': 'libxml2-2.12.9', 'version': '2.12.9'}}

REVIEWED_INPUTS = {'curl': {'CMake/Macros.cmake': {'sha256': '49f82a871d0af2cee4aafc546e4f70da5552a11b0b2d89bb675472f69120595b', 'bytes': 6315}, 'CMake/OtherTests.cmake': {'sha256': '9554ce1460c04443a7f01cac96c1eb5d7b45fe0761df48a8dc4804f97cdce1e1', 'bytes': 4852}, 'CMake/Utilities.cmake': {'sha256': '322f055be87dc33f76d8f0330332af78868c4b90380450e4c4e5f82e32d4567f', 'bytes': 3156}, 'CMake/win32-cache.cmake': {'sha256': '3a299ed264294d8552e134036251e093860bddf51b6f40da44959f8257b4b23d', 'bytes': 6694}, 'CMakeLists.txt': {'sha256': 'b7fb6401b5c2992c589f4e325cb00e96e3534a86a789166172d9f21ad460b2f5', 'bytes': 94040}, 'lib/CMakeLists.txt': {'sha256': 'e270a3c27d22b0d091cf94ccf4f6e94904bb20af923bb4ab04911ae2b229f8a8', 'bytes': 13969}, 'lib/Makefile.inc': {'sha256': 'e0d06de42dc8fe4f96fcc87a9a7c8861e5bc59b6a33fdb8c4fdac4440dd6902c', 'bytes': 9918}, 'lib/curl_config.h.cmake': {'sha256': '5d6a72c1005fbe86c8a9e99cdea81d7b7029cd5027bfaae4158e97659403fcd1', 'bytes': 22706}}, 'harfbuzz': {'CMakeLists.txt': {'sha256': 'a0ce4c0575f3dad0dce9a8bb453514c60e4c7d1ff60b53bbedd86d9cb4cb4564', 'bytes': 34310}, 'replace-enum-strings.cmake': {'sha256': '61ef04a7876f3c511693a546dbe3e234b86e16ce4d41250651a5d3da025ee98c', 'bytes': 352}, 'src/harfbuzz-config.cmake.in': {'sha256': '69e99d4ed76639b8cf6335fd6176f9f4691eb10b9e85bc318d94f2f22958f609', 'bytes': 1455}, 'src/hb-features.h.in': {'sha256': 'e3986077ac763cd298932ba68a9be76c6b92d8cde710b52909199c1b444ad246', 'bytes': 2661}, 'src/hb-version.h.in': {'sha256': 'cad5fd6b8063e4e000e405eac9e10347eee1d815c00aa7f1899389f5bcfb155a', 'bytes': 2653}}, 'nghttp2': {'CMakeLists.txt': {'sha256': '92cba43d99152440024e6717f1a8a5b5c162e5a64bfad2c744ff254daa551011', 'bytes': 18869}, 'CMakeOptions.txt': {'sha256': 'eab9f36dd612f4a6c022e0afc849aaa36c64d55553acaedf8d359079a1a44e32', 'bytes': 1369}, 'cmake/Version.cmake': {'sha256': 'f6c4cf4eea346e01a2456d749b543d5be161f5f5706763c7c8ea641ada3afd19', 'bytes': 478}, 'cmakeconfig.h.in': {'sha256': 'c0e1d97af96baab0ef0f37ef3e402ce40defea46dbf2e416c682a2e0f0959614', 'bytes': 3356}, 'lib/CMakeLists.txt': {'sha256': '4065ef9b6f19ed3d90103d2f00408449b5f5cc7eb6687964764c15ccbff88367', 'bytes': 2858}, 'lib/includes/CMakeLists.txt': {'sha256': 'b0f4ea160dcc28bbe8a553128613ebf1bf72447751567fc0ea7e2292ddb39604', 'bytes': 144}, 'lib/includes/nghttp2/nghttp2ver.h.in': {'sha256': '7f92a07886777c4f6c6f0b2f48e5e3347ee1057fd7b7313b232b5e7ea409b350', 'bytes': 1629}}, 'xml2': {'CMakeLists.txt': {'sha256': '000b0499c52c901ab51aa69e70ea927da0f570f4bea1170d08a17431d5336c08', 'bytes': 23943}, 'config.h.cmake.in': {'sha256': 'a1197f0dc6302ec1a008f12b95a0fce8821a39a1b180a2d49479691e8692efa7', 'bytes': 3634}, 'include/libxml/xmlversion.h.in': {'sha256': 'b29198c3f85598cfb115226b039ebdb5af301f87be65167461c64c45f61660a2', 'bytes': 9705}, 'libxml2-config.cmake.cmake.in': {'sha256': 'da185b14aaa05b98c10903c636a8685cc70cfd281bb81b896805c5f2057335ad', 'bytes': 7060}}}

REQUIRED_MEMBERS = {'harfbuzz': ['CMakeLists.txt', 'meson.build', 'replace-enum-strings.cmake', 'src/harfbuzz-config.cmake.in', 'src/harfbuzz.cc', 'src/hb-aat-layout.h', 'src/hb-aat.h', 'src/hb-blob.h', 'src/hb-buffer.h', 'src/hb-common.h', 'src/hb-cplusplus.hh', 'src/hb-deprecated.h', 'src/hb-draw.h', 'src/hb-face.h', 'src/hb-features.h.in', 'src/hb-font.h', 'src/hb-icu.cc', 'src/hb-icu.h', 'src/hb-map.h', 'src/hb-ot-color.h', 'src/hb-ot-deprecated.h', 'src/hb-ot-font.h', 'src/hb-ot-layout.h', 'src/hb-ot-math.h', 'src/hb-ot-meta.h', 'src/hb-ot-metrics.h', 'src/hb-ot-name.h', 'src/hb-ot-shape.h', 'src/hb-ot-var.h', 'src/hb-ot.h', 'src/hb-paint.h', 'src/hb-set.h', 'src/hb-shape-plan.h', 'src/hb-shape.h', 'src/hb-style.h', 'src/hb-unicode.h', 'src/hb-version.h', 'src/hb-version.h.in', 'src/hb.h'], 'xml2': ['CMakeLists.txt', 'HTMLparser.c', 'HTMLtree.c', 'SAX.c', 'SAX2.c', 'buf.c', 'c14n.c', 'catalog.c', 'chvalid.c', 'config.h.cmake.in', 'configure.ac', 'debugXML.c', 'dict.c', 'encoding.c', 'entities.c', 'error.c', 'globals.c', 'hash.c', 'include/libxml/HTMLparser.h', 'include/libxml/HTMLtree.h', 'include/libxml/SAX.h', 'include/libxml/SAX2.h', 'include/libxml/c14n.h', 'include/libxml/catalog.h', 'include/libxml/chvalid.h', 'include/libxml/debugXML.h', 'include/libxml/dict.h', 'include/libxml/encoding.h', 'include/libxml/entities.h', 'include/libxml/globals.h', 'include/libxml/hash.h', 'include/libxml/list.h', 'include/libxml/nanoftp.h', 'include/libxml/nanohttp.h', 'include/libxml/parser.h', 'include/libxml/parserInternals.h', 'include/libxml/pattern.h', 'include/libxml/relaxng.h', 'include/libxml/schemasInternals.h', 'include/libxml/schematron.h', 'include/libxml/threads.h', 'include/libxml/tree.h', 'include/libxml/uri.h', 'include/libxml/valid.h', 'include/libxml/xinclude.h', 'include/libxml/xlink.h', 'include/libxml/xmlIO.h', 'include/libxml/xmlautomata.h', 'include/libxml/xmlerror.h', 'include/libxml/xmlexports.h', 'include/libxml/xmlmemory.h', 'include/libxml/xmlmodule.h', 'include/libxml/xmlreader.h', 'include/libxml/xmlregexp.h', 'include/libxml/xmlsave.h', 'include/libxml/xmlschemas.h', 'include/libxml/xmlschemastypes.h', 'include/libxml/xmlstring.h', 'include/libxml/xmlunicode.h', 'include/libxml/xmlversion.h.in', 'include/libxml/xmlwriter.h', 'include/libxml/xpath.h', 'include/libxml/xpathInternals.h', 'include/libxml/xpointer.h', 'include/win32config.h', 'legacy.c', 'libxml2-config.cmake.cmake.in', 'list.c', 'nanoftp.c', 'nanohttp.c', 'parser.c', 'parserInternals.c', 'pattern.c', 'relaxng.c', 'schematron.c', 'threads.c', 'tree.c', 'uri.c', 'valid.c', 'win32/libxml2.rc', 'xinclude.c', 'xlink.c', 'xmlIO.c', 'xmlmemory.c', 'xmlmodule.c', 'xmlreader.c', 'xmlregexp.c', 'xmlsave.c', 'xmlschemas.c', 'xmlschemastypes.c', 'xmlstring.c', 'xmlunicode.c', 'xmlwriter.c', 'xpath.c', 'xpointer.c', 'xzlib.c'], 'nghttp2': ['CMakeLists.txt', 'CMakeOptions.txt', 'cmake/Version.cmake', 'cmakeconfig.h.in', 'lib/CMakeLists.txt', 'lib/includes/CMakeLists.txt', 'lib/includes/nghttp2/nghttp2.h', 'lib/includes/nghttp2/nghttp2ver.h.in', 'lib/nghttp2_alpn.c', 'lib/nghttp2_buf.c', 'lib/nghttp2_callbacks.c', 'lib/nghttp2_debug.c', 'lib/nghttp2_extpri.c', 'lib/nghttp2_frame.c', 'lib/nghttp2_hd.c', 'lib/nghttp2_hd_huffman.c', 'lib/nghttp2_hd_huffman_data.c', 'lib/nghttp2_helper.c', 'lib/nghttp2_http.c', 'lib/nghttp2_map.c', 'lib/nghttp2_mem.c', 'lib/nghttp2_option.c', 'lib/nghttp2_outbound_item.c', 'lib/nghttp2_pq.c', 'lib/nghttp2_priority_spec.c', 'lib/nghttp2_queue.c', 'lib/nghttp2_ratelim.c', 'lib/nghttp2_rcbuf.c', 'lib/nghttp2_session.c', 'lib/nghttp2_stream.c', 'lib/nghttp2_submit.c', 'lib/nghttp2_time.c', 'lib/nghttp2_version.c', 'lib/sfparse.c'], 'curl': ['CMake/CurlTests.c', 'CMake/Macros.cmake', 'CMake/OtherTests.cmake', 'CMake/Utilities.cmake', 'CMake/win32-cache.cmake', 'CMakeLists.txt', 'include/curl/curlver.h', 'lib/CMakeLists.txt', 'lib/Makefile.inc', 'lib/altsvc.c', 'lib/amigaos.c', 'lib/asyn-ares.c', 'lib/asyn-base.c', 'lib/asyn-thrdd.c', 'lib/bufq.c', 'lib/bufref.c', 'lib/cf-h1-proxy.c', 'lib/cf-h2-proxy.c', 'lib/cf-haproxy.c', 'lib/cf-https-connect.c', 'lib/cf-ip-happy.c', 'lib/cf-socket.c', 'lib/cfilters.c', 'lib/conncache.c', 'lib/connect.c', 'lib/content_encoding.c', 'lib/cookie.c', 'lib/cshutdn.c', 'lib/curl_addrinfo.c', 'lib/curl_config.h.cmake', 'lib/curl_endian.c', 'lib/curl_fnmatch.c', 'lib/curl_fopen.c', 'lib/curl_get_line.c', 'lib/curl_gethostname.c', 'lib/curl_gssapi.c', 'lib/curl_memrchr.c', 'lib/curl_ntlm_core.c', 'lib/curl_range.c', 'lib/curl_rtmp.c', 'lib/curl_sasl.c', 'lib/curl_sha512_256.c', 'lib/curl_sspi.c', 'lib/curl_threads.c', 'lib/curl_trc.c', 'lib/curlx/base64.c', 'lib/curlx/dynbuf.c', 'lib/curlx/fopen.c', 'lib/curlx/inet_ntop.c', 'lib/curlx/inet_pton.c', 'lib/curlx/multibyte.c', 'lib/curlx/nonblock.c', 'lib/curlx/strerr.c', 'lib/curlx/strparse.c', 'lib/curlx/timediff.c', 'lib/curlx/timeval.c', 'lib/curlx/version_win32.c', 'lib/curlx/wait.c', 'lib/curlx/warnless.c', 'lib/curlx/winapi.c', 'lib/cw-out.c', 'lib/cw-pause.c', 'lib/dict.c', 'lib/doh.c', 'lib/dynhds.c', 'lib/easy.c', 'lib/easygetopt.c', 'lib/easyoptions.c', 'lib/escape.c', 'lib/fake_addrinfo.c', 'lib/file.c', 'lib/fileinfo.c', 'lib/formdata.c', 'lib/ftp.c', 'lib/ftplistparser.c', 'lib/getenv.c', 'lib/getinfo.c', 'lib/gopher.c', 'lib/hash.c', 'lib/headers.c', 'lib/hmac.c', 'lib/hostip.c', 'lib/hostip4.c', 'lib/hostip6.c', 'lib/hsts.c', 'lib/http.c', 'lib/http1.c', 'lib/http2.c', 'lib/http_aws_sigv4.c', 'lib/http_chunks.c', 'lib/http_digest.c', 'lib/http_negotiate.c', 'lib/http_ntlm.c', 'lib/http_proxy.c', 'lib/httpsrr.c', 'lib/idn.c', 'lib/if2ip.c', 'lib/imap.c', 'lib/ldap.c', 'lib/llist.c', 'lib/macos.c', 'lib/md4.c', 'lib/md5.c', 'lib/memdebug.c', 'lib/mime.c', 'lib/mprintf.c', 'lib/mqtt.c', 'lib/multi.c', 'lib/multi_ev.c', 'lib/multi_ntfy.c', 'lib/netrc.c', 'lib/noproxy.c', 'lib/openldap.c', 'lib/parsedate.c', 'lib/pingpong.c', 'lib/pop3.c', 'lib/progress.c', 'lib/psl.c', 'lib/rand.c', 'lib/rename.c', 'lib/request.c', 'lib/rtsp.c', 'lib/select.c', 'lib/sendf.c', 'lib/setopt.c', 'lib/sha256.c', 'lib/share.c', 'lib/slist.c', 'lib/smb.c', 'lib/smtp.c', 'lib/socketpair.c', 'lib/socks.c', 'lib/socks_gssapi.c', 'lib/socks_sspi.c', 'lib/speedcheck.c', 'lib/splay.c', 'lib/strcase.c', 'lib/strdup.c', 'lib/strequal.c', 'lib/strerror.c', 'lib/system_win32.c', 'lib/telnet.c', 'lib/tftp.c', 'lib/transfer.c', 'lib/uint-bset.c', 'lib/uint-hash.c', 'lib/uint-spbset.c', 'lib/uint-table.c', 'lib/url.c', 'lib/urlapi.c', 'lib/vauth/cleartext.c', 'lib/vauth/cram.c', 'lib/vauth/digest.c', 'lib/vauth/digest_sspi.c', 'lib/vauth/gsasl.c', 'lib/vauth/krb5_gssapi.c', 'lib/vauth/krb5_sspi.c', 'lib/vauth/ntlm.c', 'lib/vauth/ntlm_sspi.c', 'lib/vauth/oauth2.c', 'lib/vauth/spnego_gssapi.c', 'lib/vauth/spnego_sspi.c', 'lib/vauth/vauth.c', 'lib/version.c', 'lib/vquic/curl_ngtcp2.c', 'lib/vquic/curl_osslq.c', 'lib/vquic/curl_quiche.c', 'lib/vquic/vquic-tls.c', 'lib/vquic/vquic.c', 'lib/vssh/curl_path.c', 'lib/vssh/libssh.c', 'lib/vssh/libssh2.c', 'lib/vtls/apple.c', 'lib/vtls/cipher_suite.c', 'lib/vtls/gtls.c', 'lib/vtls/hostcheck.c', 'lib/vtls/keylog.c', 'lib/vtls/mbedtls.c', 'lib/vtls/mbedtls_threadlock.c', 'lib/vtls/openssl.c', 'lib/vtls/rustls.c', 'lib/vtls/schannel.c', 'lib/vtls/schannel_verify.c', 'lib/vtls/vtls.c', 'lib/vtls/vtls_scache.c', 'lib/vtls/vtls_spack.c', 'lib/vtls/wolfssl.c', 'lib/vtls/x509asn1.c', 'lib/ws.c']}

PUBLIC_HEADERS = {'harfbuzz': ['src/hb-aat-layout.h', 'src/hb-aat.h', 'src/hb-blob.h', 'src/hb-buffer.h', 'src/hb-common.h', 'src/hb-cplusplus.hh', 'src/hb-deprecated.h', 'src/hb-draw.h', 'src/hb-face.h', 'src/hb-font.h', 'src/hb-icu.h', 'src/hb-map.h', 'src/hb-ot-color.h', 'src/hb-ot-deprecated.h', 'src/hb-ot-font.h', 'src/hb-ot-layout.h', 'src/hb-ot-math.h', 'src/hb-ot-meta.h', 'src/hb-ot-metrics.h', 'src/hb-ot-name.h', 'src/hb-ot-shape.h', 'src/hb-ot-var.h', 'src/hb-ot.h', 'src/hb-paint.h', 'src/hb-set.h', 'src/hb-shape-plan.h', 'src/hb-shape.h', 'src/hb-style.h', 'src/hb-unicode.h', 'src/hb-version.h', 'src/hb.h'], 'xml2': ['include/libxml/HTMLparser.h', 'include/libxml/HTMLtree.h', 'include/libxml/SAX.h', 'include/libxml/SAX2.h', 'include/libxml/c14n.h', 'include/libxml/catalog.h', 'include/libxml/chvalid.h', 'include/libxml/debugXML.h', 'include/libxml/dict.h', 'include/libxml/encoding.h', 'include/libxml/entities.h', 'include/libxml/globals.h', 'include/libxml/hash.h', 'include/libxml/list.h', 'include/libxml/nanoftp.h', 'include/libxml/nanohttp.h', 'include/libxml/parser.h', 'include/libxml/parserInternals.h', 'include/libxml/pattern.h', 'include/libxml/relaxng.h', 'include/libxml/schemasInternals.h', 'include/libxml/schematron.h', 'include/libxml/threads.h', 'include/libxml/tree.h', 'include/libxml/uri.h', 'include/libxml/valid.h', 'include/libxml/xinclude.h', 'include/libxml/xlink.h', 'include/libxml/xmlIO.h', 'include/libxml/xmlautomata.h', 'include/libxml/xmlerror.h', 'include/libxml/xmlexports.h', 'include/libxml/xmlmemory.h', 'include/libxml/xmlmodule.h', 'include/libxml/xmlreader.h', 'include/libxml/xmlregexp.h', 'include/libxml/xmlsave.h', 'include/libxml/xmlschemas.h', 'include/libxml/xmlschemastypes.h', 'include/libxml/xmlstring.h', 'include/libxml/xmlunicode.h', 'include/libxml/xmlwriter.h', 'include/libxml/xpath.h', 'include/libxml/xpathInternals.h', 'include/libxml/xpointer.h'], 'nghttp2': ['lib/includes/nghttp2/nghttp2.h']}

TEMPLATES = {
    'harfbuzz-project': r"""cmake_minimum_required(VERSION 3.12)
project(harfbuzz)
if(NOT WIN32 OR NOT MSVC OR NOT CMAKE_C_COMPILER_ID STREQUAL "Clang" OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "The fixed graph requires native Windows x86_64 clang-cl")
endif()
if(NOT CMAKE_C_COMPILER_TARGET STREQUAL "x86_64-pc-windows-msvc")
  message(FATAL_ERROR "The fixed graph requires the admitted compiler target")
endif()


message(WARN "HarfBuzz has a Meson port and tries to migrate all the other build systems to it, please consider using it as we might remove our cmake port soon.")

set(CMAKE_CXX_STANDARD 11)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

## Limit framework build to Xcode generator
if (BUILD_FRAMEWORK)
  # for a framework build on macOS, use:
  # cmake -DBUILD_FRAMEWORK=ON -Bbuild -H. -GXcode && cmake --build build
  if (NOT "${CMAKE_GENERATOR}" STREQUAL "Xcode")
    message(FATAL_ERROR
      "You should use Xcode generator with BUILD_FRAMEWORK enabled")
  endif ()
  set (CMAKE_OSX_ARCHITECTURES "$(ARCHS_STANDARD_32_64_BIT)")
  set (CMAKE_MACOSX_RPATH ON)
  set (BUILD_SHARED_LIBS ON)
endif ()


## Disallow in-source builds, as CMake generated make files can collide with autotools ones
if (NOT MSVC AND "${PROJECT_BINARY_DIR}" STREQUAL "${SOURCE_ROOT}")
  message(FATAL_ERROR
    "
In-source builds are not permitted!  Make a separate folder for"
    " building, e.g.,"
    "
  mkdir build; cd build; cmake .."
    "
Before that, remove the files created by this failed run with"
    "
  rm -rf CMakeCache.txt CMakeFiles")
endif ()


## HarfBuzz build configurations
option(HB_HAVE_CAIRO "Enable cairo interop helpers" OFF)
option(HB_HAVE_FREETYPE "Enable freetype interop helpers" OFF)
option(HB_HAVE_GRAPHITE2 "Enable Graphite2 complementary shaper" OFF)
option(HB_HAVE_GLIB "Enable glib unicode functions" OFF)
option(HB_HAVE_ICU "Enable icu unicode functions" OFF)
if (TARGET freetype)
  set (HB_HAVE_FREETYPE ON)
  add_definitions(-DHAVE_FREETYPE=1)
endif ()
if (APPLE)
  option(HB_HAVE_CORETEXT "Enable CoreText shaper backend on macOS" ON)
  set (CMAKE_MACOSX_RPATH ON)
endif ()
if (WIN32)
  option(HB_HAVE_UNISCRIBE "Enable Uniscribe shaper backend on Windows" OFF)
  option(HB_HAVE_GDI "Enable GDI integration helpers on Windows" OFF)
  option(HB_HAVE_DIRECTWRITE "Enable DirectWrite shaper backend on Windows" OFF)
endif ()
option(HB_BUILD_UTILS "Build harfbuzz utils, needs cairo, freetype, and glib properly be installed" OFF)
if (HB_BUILD_UTILS)
  set (HB_HAVE_GLIB ON)
  set (HB_HAVE_FREETYPE ON)
endif ()

option(HB_BUILD_SUBSET "Build harfbuzz-subset" ON)

option(HB_HAVE_GOBJECT "Enable GObject Bindings" OFF)
if (HB_HAVE_GOBJECT)
  set (HB_HAVE_GLIB ON)
endif ()

option(HB_HAVE_INTROSPECTION "Enable building introspection (.gir/.typelib) files" OFF)
if (HB_HAVE_INTROSPECTION)
  set (HB_HAVE_GOBJECT ON)
  set (HB_HAVE_GLIB ON)
endif ()

include_directories(AFTER
  ${SOURCE_ROOT}/src
  ${PROJECT_BINARY_DIR}/src
)

# We need Python3_EXECUTABLE to be set for running the tests...
set(Python3_FOUND FALSE) # No test/tool producer in this route.

## Functions and headers
include (CheckFunctionExists)
include (CheckIncludeFile)
include (CheckIncludeFiles)
macro (check_funcs) # Similar to AC_CHECK_FUNCS of autotools
  foreach (func_name ${ARGN})
    string(TOUPPER ${func_name} definition_to_add)
    check_function_exists(${func_name} HAVE_${definition_to_add})
    if (${HAVE_${definition_to_add}})
      add_definitions(-DHAVE_${definition_to_add})
    endif ()
  endforeach ()
endmacro ()
if (UNIX)
  list(APPEND CMAKE_REQUIRED_LIBRARIES m)
endif ()
check_funcs(atexit mprotect sysconf getpagesize mmap isatty)
check_include_file(unistd.h HAVE_UNISTD_H)
if (${HAVE_UNISTD_H})
  add_definitions(-DHAVE_UNISTD_H)
endif ()
check_include_file(sys/mman.h HAVE_SYS_MMAN_H)
if (${HAVE_SYS_MMAN_H})
  add_definitions(-DHAVE_SYS_MMAN_H)
endif ()
check_include_file(stdbool.h HAVE_STDBOOL_H)
if (${HAVE_STDBOOL_H})
  add_definitions(-DHAVE_STDBOOL_H)
endif ()

# These will be used while making pkg-config .pc files
set(PC_REQUIRES_PRIV "")
set(PC_LIBS_PRIV "")

if (NOT MSVC)
  set(THREADS_PREFER_PTHREAD_FLAG ON)
  find_package(Threads)
  if (CMAKE_USE_PTHREADS_INIT)
    add_definitions("-DHAVE_PTHREAD")
    list(APPEND THIRD_PARTY_LIBS Threads::Threads)
    list(APPEND PC_LIBS_PRIV -pthread)
  endif ()
endif ()

if (MSVC)
  add_definitions(-wd4244 -wd4267 -D_CRT_SECURE_NO_WARNINGS -D_CRT_NONSTDC_NO_WARNINGS)
  add_definitions(-bigobj)
endif ()


## Detect if we are running inside a distribution or regular repository folder
# if (EXISTS "${SOURCE_ROOT}/ChangeLog")
#   # perhaps we are on dist directory
#   set (IN_HB_DIST TRUE)
#   #set (HB_VERSION_H "${SOURCE_ROOT}/src/hb-version.h")
# endif ()

file(READ "${SOURCE_ROOT}/meson.build" MESONBUILD)
string(REGEX MATCH "version: '(([0-9]+)\\.([0-9]+)\\.([0-9]+))'," HB_VERSION_MATCH ${MESONBUILD})
set (HB_VERSION ${CMAKE_MATCH_1})
set (HB_VERSION_MAJOR ${CMAKE_MATCH_2})
set (HB_VERSION_MINOR ${CMAKE_MATCH_3})
set (HB_VERSION_MICRO ${CMAKE_MATCH_4})

## Define sources and headers of the project
set (project_sources ${SOURCE_ROOT}/src/harfbuzz.cc) # use amalgam source
set (subset_project_sources
     ${SOURCE_ROOT}/src/hb-number.cc
     ${SOURCE_ROOT}/src/hb-number.hh
     ${SOURCE_ROOT}/src/hb-ot-cff1-table.cc
     ${SOURCE_ROOT}/src/hb-ot-cff2-table.cc
     ${SOURCE_ROOT}/src/hb-ot-post-table-v2subset.hh
     ${SOURCE_ROOT}/src/hb-static.cc
     ${SOURCE_ROOT}/src/hb-subset-cff-common.cc
     ${SOURCE_ROOT}/src/hb-subset-cff-common.hh
     ${SOURCE_ROOT}/src/hb-subset-cff1.cc
     ${SOURCE_ROOT}/src/hb-subset-cff2.cc
     ${SOURCE_ROOT}/src/hb-subset-input.cc
     ${SOURCE_ROOT}/src/hb-subset-input.hh
     ${SOURCE_ROOT}/src/hb-subset-instancer-iup.hh
     ${SOURCE_ROOT}/src/hb-subset-instancer-iup.cc
     ${SOURCE_ROOT}/src/hb-subset-instancer-solver.hh
     ${SOURCE_ROOT}/src/hb-subset-instancer-solver.cc
     ${SOURCE_ROOT}/src/hb-subset-accelerator.hh
     ${SOURCE_ROOT}/src/hb-subset-plan.cc
     ${SOURCE_ROOT}/src/hb-subset-plan.hh
     ${SOURCE_ROOT}/src/hb-subset-plan-member-list.hh
     ${SOURCE_ROOT}/src/hb-subset-repacker.cc
     ${SOURCE_ROOT}/src/hb-subset.cc
     ${SOURCE_ROOT}/src/hb-subset.hh
     ${SOURCE_ROOT}/src/hb-repacker.hh
     ${SOURCE_ROOT}/src/graph/graph.hh
     ${SOURCE_ROOT}/src/graph/gsubgpos-graph.hh
     ${SOURCE_ROOT}/src/graph/gsubgpos-context.hh
     ${SOURCE_ROOT}/src/graph/gsubgpos-context.cc
     ${SOURCE_ROOT}/src/graph/coverage-graph.hh
     ${SOURCE_ROOT}/src/graph/classdef-graph.hh
     ${SOURCE_ROOT}/src/graph/pairpos-graph.hh
     ${SOURCE_ROOT}/src/graph/markbasepos-graph.hh
     ${SOURCE_ROOT}/src/graph/split-helpers.hh
     ${SOURCE_ROOT}/src/graph/serialize.hh
     ${SOURCE_ROOT}/src/OT/Color/COLR/colrv1-closure.hh
)
set (project_extra_sources)
set (project_headers
     ${SOURCE_ROOT}/src/hb-aat-layout.h
     ${SOURCE_ROOT}/src/hb-aat.h
     ${SOURCE_ROOT}/src/hb-blob.h
     ${SOURCE_ROOT}/src/hb-buffer.h
     ${SOURCE_ROOT}/src/hb-common.h
     ${SOURCE_ROOT}/src/hb-cplusplus.hh
     ${SOURCE_ROOT}/src/hb-deprecated.h
     ${SOURCE_ROOT}/src/hb-draw.h
     ${SOURCE_ROOT}/src/hb-face.h
     ${SOURCE_ROOT}/src/hb-font.h
     ${SOURCE_ROOT}/src/hb-map.h
     ${SOURCE_ROOT}/src/hb-ot-color.h
     ${SOURCE_ROOT}/src/hb-ot-deprecated.h
     ${SOURCE_ROOT}/src/hb-ot-font.h
     ${SOURCE_ROOT}/src/hb-ot-layout.h
     ${SOURCE_ROOT}/src/hb-ot-math.h
     ${SOURCE_ROOT}/src/hb-ot-meta.h
     ${SOURCE_ROOT}/src/hb-ot-metrics.h
     ${SOURCE_ROOT}/src/hb-ot-name.h
     ${SOURCE_ROOT}/src/hb-ot-shape.h
     ${SOURCE_ROOT}/src/hb-ot-var.h
     ${SOURCE_ROOT}/src/hb-ot.h
     ${SOURCE_ROOT}/src/hb-paint.h
     ${SOURCE_ROOT}/src/hb-set.h
     ${SOURCE_ROOT}/src/hb-shape-plan.h
     ${SOURCE_ROOT}/src/hb-shape.h
     ${SOURCE_ROOT}/src/hb-style.h
     ${SOURCE_ROOT}/src/hb-unicode.h
     ${SOURCE_ROOT}/src/hb-version.h
     ${SOURCE_ROOT}/src/hb.h
)
set (subset_project_headers
     ${SOURCE_ROOT}/src/hb-subset.h
     ${SOURCE_ROOT}/src/hb-subset-repacker.h
)

## Find and include needed header folders and libraries
if (HB_HAVE_FREETYPE AND NOT TARGET freetype)
  include (FindFreetype)
  if (NOT FREETYPE_FOUND)
    message(FATAL_ERROR "HB_HAVE_FREETYPE was set, but we failed to find it. Maybe add a CMAKE_PREFIX_PATH= to your Freetype2 install prefix")
  endif ()

  list(APPEND THIRD_PARTY_LIBS ${FREETYPE_LIBRARIES})
  include_directories(AFTER ${FREETYPE_INCLUDE_DIRS})
  add_definitions(-DHAVE_FREETYPE=1)

  list(APPEND project_headers ${SOURCE_ROOT}/src/hb-ft.h)

  # So check_funcs can find its headers
  set (CMAKE_REQUIRED_INCLUDES ${CMAKE_REQUIRED_INCLUDES} ${FREETYPE_INCLUDE_DIRS})
  set (CMAKE_REQUIRED_LIBRARIES ${CMAKE_REQUIRED_LIBRARIES} ${FREETYPE_LIBRARIES})

  check_funcs(FT_Get_Var_Blend_Coordinates FT_Set_Var_Blend_Coordinates FT_Done_MM_Var)
endif ()

if (HB_HAVE_FREETYPE)
  list(APPEND PC_REQUIRES_PRIV "freetype2 >= 12.0.6")
endif ()

if (HB_HAVE_GRAPHITE2)
  add_definitions(-DHAVE_GRAPHITE2)

  find_path(GRAPHITE2_INCLUDE_DIR graphite2/Font.h)
  find_library(GRAPHITE2_LIBRARY graphite2)

  include_directories(${GRAPHITE2_INCLUDE_DIR})

  list(APPEND project_headers ${SOURCE_ROOT}/src/hb-graphite2.h)

  list(APPEND THIRD_PARTY_LIBS ${GRAPHITE2_LIBRARY})

  list(APPEND PC_REQUIRES_PRIV "graphite2 >= 1.2.0")

  mark_as_advanced(GRAPHITE2_INCLUDE_DIR GRAPHITE2_LIBRARY)
endif ()

if (HB_HAVE_GLIB)
  add_definitions(-DHAVE_GLIB)

  # https://github.com/WebKit/webkit/blob/master/Source/cmake/FindGLIB.cmake
  find_package(PkgConfig)
  pkg_check_modules(PC_GLIB QUIET glib-2.0)

  find_library(GLIB_LIBRARIES NAMES glib-2.0 HINTS ${PC_GLIB_LIBDIR} ${PC_GLIB_LIBRARY_DIRS})
  find_path(GLIBCONFIG_INCLUDE_DIR NAMES glibconfig.h HINTS ${PC_LIBDIR} ${PC_LIBRARY_DIRS} ${PC_GLIB_INCLUDEDIR} ${PC_GLIB_INCLUDE_DIRS} PATH_SUFFIXES glib-2.0/include)
  find_path(GLIB_INCLUDE_DIR NAMES glib.h HINTS ${PC_GLIB_INCLUDEDIR} ${PC_GLIB_INCLUDE_DIRS} PATH_SUFFIXES glib-2.0)

  include_directories(${GLIBCONFIG_INCLUDE_DIR} ${GLIB_INCLUDE_DIR})

  list(APPEND project_headers ${SOURCE_ROOT}/src/hb-glib.h)

  list(APPEND THIRD_PARTY_LIBS ${GLIB_LIBRARIES})

  list(APPEND PC_REQUIRES_PRIV "glib-2.0 >= 2.19.1")

  mark_as_advanced(GLIB_LIBRARIES GLIBCONFIG_INCLUDE_DIR GLIB_INCLUDE_DIR)
endif ()

if (HB_HAVE_ICU)
  add_definitions(-DHAVE_ICU)

  find_package(ICU REQUIRED COMPONENTS uc)

  if (ICU_VERSION VERSION_GREATER_EQUAL 75.1)
    set(CMAKE_CXX_STANDARD 17)
  endif ()

  list(APPEND project_headers ${SOURCE_ROOT}/src/hb-icu.h)

  list(APPEND THIRD_PARTY_LIBS ICU::uc)
endif ()

if (APPLE AND HB_HAVE_CORETEXT)
  # Apple Advanced Typography
  add_definitions(-DHAVE_CORETEXT)

  list(APPEND project_headers ${SOURCE_ROOT}/src/hb-coretext.h)

  if (HB_IOS)
    find_library(COREFOUNDATION CoreFoundation)
    if (COREFOUNDATION)
      list(APPEND THIRD_PARTY_LIBS ${COREFOUNDATION})
      list(APPEND PC_LIBS_PRIV "-framework CoreFoundation")
    endif ()
    mark_as_advanced(COREFOUNDATION)

    find_library(CORETEXT CoreText)
    if (CORETEXT)
      list(APPEND THIRD_PARTY_LIBS ${CORETEXT})
      list(APPEND PC_LIBS_PRIV "-framework CoreText")
    endif ()
    mark_as_advanced(CORETEXT)

    find_library(COREGRAPHICS CoreGraphics)
    if (COREGRAPHICS)
      list(APPEND THIRD_PARTY_LIBS ${COREGRAPHICS})
      list(APPEND PC_LIBS_PRIV "-framework CoreGraphics")
    endif ()
    mark_as_advanced(COREGRAPHICS)
  else ()
    find_library(APPLICATION_SERVICES_FRAMEWORK ApplicationServices)
    if (APPLICATION_SERVICES_FRAMEWORK)
      list(APPEND THIRD_PARTY_LIBS ${APPLICATION_SERVICES_FRAMEWORK})
      list(APPEND PC_LIBS_PRIV "-framework ApplicationServices")
    endif ()

    mark_as_advanced(APPLICATION_SERVICES_FRAMEWORK)
  endif ()
endif ()

if (WIN32 AND HB_HAVE_GDI)
  add_definitions(-DHAVE_GDI)
  list(APPEND project_headers ${SOURCE_ROOT}/src/hb-gdi.h)
  list(APPEND THIRD_PARTY_LIBS gdi32)
  list(APPEND PC_LIBS_PRIV -lgdi32)
endif ()

if (WIN32 AND HB_HAVE_UNISCRIBE)
  add_definitions(-DHAVE_UNISCRIBE)
  list(APPEND project_headers ${SOURCE_ROOT}/src/hb-uniscribe.h)
  list(APPEND THIRD_PARTY_LIBS usp10 gdi32 rpcrt4)
  list(APPEND PC_LIBS_PRIV -lusp10 -lgdi32 -lrpcrt4)
endif ()

if (WIN32 AND HB_HAVE_DIRECTWRITE)
  if (CMAKE_VERSION VERSION_GREATER 3.12)
    check_include_files("windows.h;dwrite_1.h" HAVE_DWRITE_1_H LANGUAGE CXX)
  else ()
    check_include_files("windows.h;dwrite_1.h" HAVE_DWRITE_1_H)
  endif ()
  if (NOT HAVE_DWRITE_1_H)
    message(FATAL_ERROR "DirectWrite was enabled explicitly, but required header is missing")
  endif ()
  add_definitions(-DHAVE_DIRECTWRITE)
  list(APPEND project_headers ${SOURCE_ROOT}/src/hb-directwrite.h)
endif ()

if (HB_HAVE_CAIRO)
  # https://github.com/WebKit/webkit/blob/master/Source/cmake/FindCairo.cmake
  find_package(PkgConfig)
  pkg_check_modules(PC_CAIRO QUIET cairo)

  find_path(CAIRO_INCLUDE_DIRS NAMES cairo.h HINTS ${PC_CAIRO_INCLUDEDIR} ${PC_CAIRO_INCLUDE_DIRS} PATH_SUFFIXES cairo)
  find_library(CAIRO_LIBRARIESNAMES cairo HINTS ${PC_CAIRO_LIBDIR} ${PC_CAIRO_LIBRARY_DIRS})
  if (NOT CAIRO_LIBRARIESNAMES)
    message(FATAL_ERROR "HB_HAVE_CAIRO is ON but Cairo libraries are not found")
  endif()
  include_directories(${CAIRO_INCLUDE_DIRS})
  mark_as_advanced(CAIRO_INCLUDE_DIRS CAIRO_LIBRARIESNAMES)
  add_definitions(-DHAVE_CAIRO=1)
  list(APPEND project_headers ${SOURCE_ROOT}/src/hb-cairo.h)
  list(APPEND THIRD_PARTY_LIBS ${CAIRO_LIBRARIESNAMES})
endif()

if (HB_HAVE_GOBJECT)
  add_definitions(-DHAVE_GOBJECT)
  include (FindPerl)

  # Use the hints from glib-2.0.pc to find glib-mkenums
  find_package(PkgConfig)
  pkg_check_modules(PC_GLIB QUIET glib-2.0)
  find_program(GLIB_MKENUMS glib-mkenums
    HINTS ${PC_glib_mkenums}
  )
  set (GLIB_MKENUMS_CMD)

  if (WIN32 AND NOT MINGW)
    # In Visual Studio builds, shebang lines are not supported
    # in the standard cmd.exe shell that we use, so we need to
    # first determine whether glib-mkenums is a Python or PERL
    # script
    execute_process(COMMAND "${Python3_EXECUTABLE}" "${GLIB_MKENUMS}" --version
      RESULT_VARIABLE GLIB_MKENUMS_PYTHON
      OUTPUT_QUIET ERROR_QUIET
    )
    if (GLIB_MKENUMS_PYTHON EQUAL 0)
      message("${GLIB_MKENUMS} is a Python script.")
      set (GLIB_MKENUMS_CMD "${Python3_EXECUTABLE}" "${GLIB_MKENUMS}")
    else ()
      execute_process(COMMAND "${PERL_EXECUTABLE}" "${GLIB_MKENUMS}" --version
        RESULT_VARIABLE GLIB_MKENUMS_PERL
        OUTPUT_QUIET ERROR_QUIET
      )
      if (GLIB_MKENUMS_PERL EQUAL 0)
        message("${GLIB_MKENUMS} is a PERL script.")
        set (GLIB_MKENUMS_CMD "${PERL_EXECUTABLE}" "${GLIB_MKENUMS}")
      endif ()
      if (NOT GLIB_MKENUMS_PERL EQUAL 0 AND NOT GLIB_MKENUMS_PYTHON EQUAL 0)
        message(FATAL_ERROR "Unable to determine type of glib-mkenums script")
      endif ()
    endif ()
  else ()
    set (GLIB_MKENUMS_CMD "${GLIB_MKENUMS}")
  endif ()
  if (NOT GLIB_MKENUMS_CMD)
    message(FATAL_ERROR "HB_HAVE_GOBJECT was set, but we failed to find glib-mkenums, which is required")
  endif ()

  pkg_check_modules(PC_GOBJECT QUIET gobject-2.0)

  find_library(GOBJECT_LIBRARIES NAMES gobject-2.0 HINTS ${PC_GLIB_LIBDIR} ${PC_GLIB_LIBRARY_DIRS})
  find_path(GOBJECT_INCLUDE_DIR NAMES glib-object.h HINTS ${PC_GLIB_INCLUDEDIR} ${PC_GLIB_INCLUDE_DIRS} PATH_SUFFIXES glib-2.0)

  include_directories(${GOBJECTCONFIG_INCLUDE_DIR} ${GOBJECT_INCLUDE_DIR})
  mark_as_advanced(GOBJECT_LIBRARIES GOBJECT_INCLUDE_DIR)

  list(APPEND hb_gobject_sources ${SOURCE_ROOT}/src/hb-gobject-structs.cc)
  list(APPEND hb_gobject_gen_sources
    ${CMAKE_CURRENT_BINARY_DIR}/src/hb-gobject-enums.cc
  )
  list(APPEND hb_gobject_structs_headers
    ${SOURCE_ROOT}/src/hb-gobject-structs.h
  )
  list(APPEND hb_gobject_headers
    ${SOURCE_ROOT}/src/hb-gobject.h
    ${hb_gobject_structs_headers}
  )
  list(APPEND hb_gobject_gen_headers
    ${CMAKE_CURRENT_BINARY_DIR}/src/hb-gobject-enums.h
  )

  add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/src/hb-gobject-enums.h
    COMMAND ${GLIB_MKENUMS_CMD}
      --template=${SOURCE_ROOT}/src/hb-gobject-enums.h.tmpl
      --identifier-prefix hb_
      --symbol-prefix hb_gobject
      ${hb_gobject_structs_headers}
      ${project_headers}
      > ${CMAKE_CURRENT_BINARY_DIR}/src/hb-gobject-enums.h.tmp
    COMMAND "${CMAKE_COMMAND}"
      "-DENUM_INPUT_SRC=${CMAKE_CURRENT_BINARY_DIR}/src/hb-gobject-enums.h.tmp"
      "-DENUM_OUTPUT_SRC=${CMAKE_CURRENT_BINARY_DIR}/src/hb-gobject-enums.h"
      -P ${SOURCE_ROOT}/replace-enum-strings.cmake
    DEPENDS ${SOURCE_ROOT}/src/hb-gobject-enums.h.tmpl
      ${hb_gobject_header}
      ${project_headers}
  )

  add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/src/hb-gobject-enums.cc
    COMMAND ${GLIB_MKENUMS_CMD}
      --template=${SOURCE_ROOT}/src/hb-gobject-enums.cc.tmpl
      --identifier-prefix hb_
      --symbol-prefix hb_gobject
      ${hb_gobject_header}
      ${project_headers}
      > ${CMAKE_CURRENT_BINARY_DIR}/src/hb-gobject-enums.cc.tmp
    COMMAND "${CMAKE_COMMAND}"
      "-DENUM_INPUT_SRC=${CMAKE_CURRENT_BINARY_DIR}/src/hb-gobject-enums.cc.tmp"
      "-DENUM_OUTPUT_SRC=${CMAKE_CURRENT_BINARY_DIR}/src/hb-gobject-enums.cc"
      -P ${SOURCE_ROOT}/replace-enum-strings.cmake
    DEPENDS ${SOURCE_ROOT}/src/hb-gobject-enums.cc.tmpl
      ${CMAKE_CURRENT_BINARY_DIR}/src/hb-gobject-enums.h
      ${hb_gobject_header}
      ${project_headers}
  )
endif ()


## Define harfbuzz library
add_library(harfbuzz ${project_sources} ${project_extra_sources} ${project_headers})
target_link_libraries(harfbuzz ${THIRD_PARTY_LIBS})
target_include_directories(harfbuzz PUBLIC
                           "$<BUILD_INTERFACE:${SOURCE_ROOT}/src>"
                           "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}/harfbuzz>")
if (HB_HAVE_FREETYPE AND TARGET freetype)
  target_link_libraries(harfbuzz freetype)
endif ()


## Define harfbuzz-icu library
if (HB_HAVE_ICU)
  add_library(harfbuzz-icu ${SOURCE_ROOT}/src/hb-icu.cc ${SOURCE_ROOT}/src/hb-icu.h)
  add_dependencies(harfbuzz-icu harfbuzz)
  target_link_libraries(harfbuzz-icu harfbuzz ${THIRD_PARTY_LIBS})

  if (BUILD_SHARED_LIBS)
    set_target_properties(harfbuzz harfbuzz-icu PROPERTIES VISIBILITY_INLINES_HIDDEN TRUE)
  endif ()
endif ()


## Define harfbuzz-subset library
if (HB_BUILD_SUBSET)
  add_library(harfbuzz-subset ${subset_project_sources} ${subset_project_headers})
  list(APPEND project_headers ${SOURCE_ROOT}/src/hb-subset.h ${SOURCE_ROOT}/src/hb-subset-repacker.h)
  add_dependencies(harfbuzz-subset harfbuzz)
  target_link_libraries(harfbuzz-subset harfbuzz ${THIRD_PARTY_LIBS})

  if (BUILD_SHARED_LIBS)
    set_target_properties(harfbuzz harfbuzz-subset PROPERTIES VISIBILITY_INLINES_HIDDEN TRUE)
  endif ()
endif ()

if (UNIX OR MINGW OR VITA)
  # Make symbols link locally
  include (CheckCXXCompilerFlag)
  CHECK_CXX_COMPILER_FLAG(-Bsymbolic-functions CXX_SUPPORTS_FLAG_BSYMB_FUNCS)
  if (CXX_SUPPORTS_FLAG_BSYMB_FUNCS)
    link_libraries(-Bsymbolic-functions)
  endif ()

  # As of CMake 3.0.0, the compiler id for Apple-provided Clang is now "AppleClang";
  # thus we use MATCHES instead of STREQUAL to include either regular Clang or AppleClang
  if (CMAKE_CXX_COMPILER_ID MATCHES "Clang" OR CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
    # Make sure we don't link to libstdc++
    set (CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fno-rtti -fno-exceptions")
    set (CMAKE_CXX_IMPLICIT_LINK_LIBRARIES "m") # libm
    set (CMAKE_CXX_IMPLICIT_LINK_DIRECTORIES "")
    set_target_properties(harfbuzz PROPERTIES LINKER_LANGUAGE C)
    if (HB_BUILD_SUBSET)
      set_target_properties(harfbuzz-subset PROPERTIES LINKER_LANGUAGE C)
    endif ()

    # No threadsafe statics as we do it ourselves
    set (CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -fno-threadsafe-statics")
  endif ()

  CHECK_CXX_COMPILER_FLAG("-std=c++11" COMPILER_SUPPORTS_CXX11)
  if (COMPILER_SUPPORTS_CXX11)
    set (CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11")
  else()
    message(STATUS "The compiler ${CMAKE_CXX_COMPILER} has no C++11 support. Please use a different C++ compiler.")
  endif()
endif ()


## Define harfbuzz-gobject library
if (HB_HAVE_GOBJECT)
  add_library(harfbuzz-gobject
    ${hb_gobject_sources}
    ${hb_gobject_gen_sources}
    ${hb_gobject_headers}
    ${hb_gobject_gen_headers}
  )
  include_directories(BEFORE ${CMAKE_CURRENT_BINARY_DIR}/src)
  add_dependencies(harfbuzz-gobject harfbuzz)
  target_link_libraries(harfbuzz-gobject harfbuzz ${GOBJECT_LIBRARIES} ${THIRD_PARTY_LIBS})

  if (BUILD_SHARED_LIBS)
    set_target_properties(harfbuzz-gobject PROPERTIES VISIBILITY_INLINES_HIDDEN TRUE)
  endif ()
endif ()

## Define harfbuzz-cairo library
if (HB_HAVE_CAIRO)
  include_directories(${CAIRO_INCLUDE_DIRS})
  add_library(harfbuzz-cairo ${SOURCE_ROOT}/src/hb-cairo.cc ${SOURCE_ROOT}/src/hb-static.cc ${SOURCE_ROOT}/src/hb-cairo.h)
  add_dependencies(harfbuzz-cairo harfbuzz)
  target_link_libraries(harfbuzz-cairo harfbuzz ${THIRD_PARTY_LIBS})

  if (BUILD_SHARED_LIBS)
    set_target_properties(harfbuzz-cairo PROPERTIES VISIBILITY_INLINES_HIDDEN TRUE)
  endif ()
endif()

if (BUILD_SHARED_LIBS AND WIN32 AND NOT MINGW)
  add_definitions("-DHB_DLL_EXPORT")
endif ()


# Source-owned exact static install policy; no upstream tool or pkg-config install.
include(GNUInstallDirs)
file(READ "${SOURCE_ROOT}/src/hb-features.h.in" feature_h_in)
foreach(arg cairo coretext directwrite freetype gdi glib gobject graphite icu uniscribe wasm)
  string(TOUPPER ${arg} feature_caps)
  if(HB_HAVE_${feature_caps})
    set(feature_outstring "#define HB_HAS_${feature_caps} 1")
  else()
    set(feature_outstring "/* #undef HB_HAS_${feature_caps} */")
  endif()
  string(REPLACE "#mesondefine HB_HAS_${feature_caps}" "${feature_outstring}" feature_h_in "${feature_h_in}")
endforeach()
file(MAKE_DIRECTORY "${PROJECT_BINARY_DIR}/src")
file(WRITE "${PROJECT_BINARY_DIR}/src/hb-features.h" "${feature_h_in}")
foreach(target harfbuzz harfbuzz-icu)
  set_target_properties(${target} PROPERTIES PREFIX "" SUFFIX ".lib" DEBUG_POSTFIX "" MSVC_RUNTIME_LIBRARY "MultiThreaded")
  target_compile_definitions(${target} PRIVATE U_STATIC_IMPLEMENTATION)
endforeach()
install(TARGETS harfbuzz harfbuzz-icu ARCHIVE DESTINATION lib)
install(FILES ${project_headers} "${PROJECT_BINARY_DIR}/src/hb-features.h" DESTINATION include/harfbuzz)
""",
    'xml2-project': r"""cmake_minimum_required(VERSION 3.18)

file(STRINGS "${SOURCE_ROOT}/configure.ac" CONFIGURE_AC_LINES)
foreach(line ${CONFIGURE_AC_LINES})
	if(line MATCHES [[^m4_define\(\[(MAJOR_VERSION|MINOR_VERSION|MICRO_VERSION)\],[ \t]*([0-9]+)\)$]])
		set(LIBXML_${CMAKE_MATCH_1} ${CMAKE_MATCH_2})
	elseif(line MATCHES "^(LIBXML_MAJOR_VERSION|LIBXML_MINOR_VERSION|LIBXML_MICRO_VERSION)=([0-9]+)$")
		set(${CMAKE_MATCH_1} ${CMAKE_MATCH_2})
	endif()
endforeach()
set(VERSION "${LIBXML_MAJOR_VERSION}.${LIBXML_MINOR_VERSION}.${LIBXML_MICRO_VERSION}")

project(libxml2 VERSION ${VERSION} LANGUAGES C)
if(NOT WIN32 OR NOT MSVC OR NOT CMAKE_C_COMPILER_ID STREQUAL "Clang" OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "The fixed graph requires native Windows x86_64 clang-cl")
endif()
if(NOT CMAKE_C_COMPILER_TARGET STREQUAL "x86_64-pc-windows-msvc")
  message(FATAL_ERROR "The fixed graph requires the admitted compiler target")
endif()


include(CheckCSourceCompiles)
include(CheckFunctionExists)
include(CheckIncludeFiles)
include(CheckLibraryExists)
include(CheckLinkerFlag)
include(CheckStructHasMember)
include(CheckSymbolExists)
include(CMakePackageConfigHelpers)

include(GNUInstallDirs)

option(BUILD_SHARED_LIBS "Build shared libraries" ON)
set(LIBXML2_WITH_AUTOMATA ON)
option(LIBXML2_WITH_C14N "Add the Canonicalization support" ON)
option(LIBXML2_WITH_CATALOG "Add the Catalog support" ON)
option(LIBXML2_WITH_DEBUG "Add the debugging module" ON)
set(LIBXML2_WITH_EXPR ON)
option(LIBXML2_WITH_FTP "Add the FTP support" OFF)
option(LIBXML2_WITH_HTML "Add the HTML support" ON)
option(LIBXML2_WITH_HTTP "Add the HTTP support" ON)
option(LIBXML2_WITH_ICONV "Add ICONV support" ON)
option(LIBXML2_WITH_ICU "Add ICU support" OFF)
option(LIBXML2_WITH_ISO8859X "Add ISO8859X support if no iconv" ON)
option(LIBXML2_WITH_LEGACY "Add deprecated APIs for compatibility" OFF)
option(LIBXML2_WITH_LZMA "Use liblzma" ON)
option(LIBXML2_WITH_MEM_DEBUG "Add the memory debugging module" OFF)
option(LIBXML2_WITH_MODULES "Add the dynamic modules support" ON)
option(LIBXML2_WITH_OUTPUT "Add the serialization support" ON)
option(LIBXML2_WITH_PATTERN "Add the xmlPattern selection interface" ON)
option(LIBXML2_WITH_PROGRAMS "Build programs" ON)
option(LIBXML2_WITH_PUSH "Add the PUSH parser interfaces" ON)
option(LIBXML2_WITH_PYTHON "Build Python bindings" ON)
option(LIBXML2_WITH_READER "Add the xmlReader parsing interface" ON)
option(LIBXML2_WITH_REGEXPS "Add Regular Expressions support" ON)
option(LIBXML2_WITH_SAX1 "Add the older SAX1 interface" ON)
option(LIBXML2_WITH_SCHEMAS "Add Relax-NG and Schemas support" ON)
option(LIBXML2_WITH_SCHEMATRON "Add Schematron support" ON)
option(LIBXML2_WITH_TESTS "Build tests" ON)
option(LIBXML2_WITH_THREADS "Add multithread support" ON)
option(LIBXML2_WITH_THREAD_ALLOC "Add per-thread memory" OFF)
option(LIBXML2_WITH_TLS "Enable thread-local storage" OFF)
option(LIBXML2_WITH_TREE "Add the DOM like tree manipulation APIs" ON)
set(LIBXML2_WITH_TRIO OFF)
set(LIBXML2_WITH_UNICODE ON)
option(LIBXML2_WITH_VALID "Add the DTD validation support" ON)
option(LIBXML2_WITH_WRITER "Add the xmlWriter saving interface" ON)
option(LIBXML2_WITH_XINCLUDE "Add the XInclude support" ON)
option(LIBXML2_WITH_XPATH "Add the XPATH support" ON)
option(LIBXML2_WITH_XPTR "Add the XPointer support" ON)
option(LIBXML2_WITH_XPTR_LOCS "Add support for XPointer locations" OFF)
option(LIBXML2_WITH_ZLIB "Use libz" ON)
set(LIBXML2_XMLCONF_WORKING_DIR ${CMAKE_CURRENT_BINARY_DIR} CACHE PATH "Working directory for XML Conformance Test Suite")

if(LIBXML2_WITH_PYTHON)
	check_include_files(unistd.h HAVE_UNISTD_H)
	check_symbol_exists(F_GETFL fcntl.h HAVE_F_GETFL)
	find_package(Python COMPONENTS Interpreter Development REQUIRED)
        #set(LIBXML2_PYTHON_INSTALL_DIR ${Python_SITEARCH} CACHE PATH "Python bindings install directory")
        set(LIBXML2_PYTHON_INSTALL_DIR "${CMAKE_INSTALL_PREFIX}/python"
	    CACHE PATH "Python bindings install directory")
endif()

foreach(VARIABLE IN ITEMS WITH_AUTOMATA WITH_C14N WITH_CATALOG WITH_DEBUG WITH_EXPR WITH_FTP WITH_HTML WITH_HTTP WITH_ICONV WITH_ICU WITH_ISO8859X WITH_LEGACY WITH_LZMA WITH_MEM_DEBUG WITH_MODULES WITH_OUTPUT WITH_PATTERN WITH_PUSH WITH_READER WITH_REGEXPS WITH_SAX1 WITH_SCHEMAS WITH_SCHEMATRON WITH_THREADS WITH_THREAD_ALLOC WITH_TREE WITH_TRIO WITH_UNICODE WITH_VALID WITH_WRITER WITH_XINCLUDE WITH_XPATH WITH_XPTR WITH_XPTR_LOCS WITH_ZLIB)
	if(LIBXML2_${VARIABLE})
		set(${VARIABLE} 1)
	else()
		set(${VARIABLE} 0)
	endif()
endforeach()

set(LIBXML_VERSION ${VERSION})
set(LIBXML_VERSION_EXTRA "")
math(EXPR LIBXML_VERSION_NUMBER "
    ${LIBXML_MAJOR_VERSION} * 10000 +
    ${LIBXML_MINOR_VERSION} * 100 +
    ${LIBXML_MICRO_VERSION}
")

set(MODULE_EXTENSION "${CMAKE_SHARED_LIBRARY_SUFFIX}")

set(PACKAGE "libxml2")
set(PACKAGE_NAME "libxml2")
set(PACKAGE_STRING "libxml2 ${VERSION}")
set(PACKAGE_TARNAME "libxml2")
set(PACKAGE_URL "https://gitlab.gnome.org/GNOME/libxml2")
set(PACKAGE_VERSION ${VERSION})

if(LIBXML2_WITH_ICONV)
	find_package(Iconv REQUIRED)
endif()

if(LIBXML2_WITH_ICU)
	find_package(ICU REQUIRED COMPONENTS data i18n uc)
endif()

if(LIBXML2_WITH_LZMA)
	find_package(LibLZMA REQUIRED)
endif()

# Source-owned finite CMake 3.31.6 Win32 thread policy. No probe result is set.
if(NOT "${CMAKE_SYSTEM_NAME}" STREQUAL "Windows" OR
   NOT "${CMAKE_HOST_SYSTEM_NAME}" STREQUAL "Windows" OR NOT WIN32 OR NOT MSVC)
  message(FATAL_ERROR "SOURCE:xml2-native-windows-thread-profile")
endif()
if(NOT LIBXML2_WITH_THREADS)
  message(FATAL_ERROR "SOURCE:xml2-required-thread-policy-disabled")
endif()
if(TARGET Threads::Threads)
  message(FATAL_ERROR "SOURCE:xml2-preexisting-thread-target")
endif()
if(NOT "${CMAKE_MODULE_PATH}" STREQUAL "${PROJECT_ROOT}/modules" OR
   EXISTS "${PROJECT_ROOT}/modules/FindThreads.cmake")
  message(FATAL_ERROR "SOURCE:xml2-shadowed-thread-module")
endif()
if(DEFINED CMAKE_FIND_PACKAGE_REDIRECTS_DIR)
  if(EXISTS "${CMAKE_FIND_PACKAGE_REDIRECTS_DIR}/threads-config.cmake" OR
     EXISTS "${CMAKE_FIND_PACKAGE_REDIRECTS_DIR}/ThreadsConfig.cmake")
    message(FATAL_ERROR "SOURCE:xml2-redirected-thread-package")
  endif()
endif()
# Join the module resource to the complete held H2 host inventory before I/O.
set(_foundation_xml2_host_root "${FOUNDATION_XML2_HOST_ROOT}")
set(_foundation_xml2_cmake_root "${CMAKE_ROOT}")
cmake_path(IS_ABSOLUTE _foundation_xml2_host_root _foundation_xml2_host_absolute)
cmake_path(IS_ABSOLUTE _foundation_xml2_cmake_root _foundation_xml2_cmake_absolute)
cmake_path(NORMAL_PATH _foundation_xml2_host_root OUTPUT_VARIABLE _foundation_xml2_host_normal)
cmake_path(NORMAL_PATH _foundation_xml2_cmake_root OUTPUT_VARIABLE _foundation_xml2_cmake_normal)
if(NOT _foundation_xml2_host_absolute OR NOT _foundation_xml2_cmake_absolute OR
   NOT "${_foundation_xml2_host_root}" STREQUAL "${_foundation_xml2_host_normal}" OR
   NOT "${_foundation_xml2_cmake_root}" STREQUAL "${_foundation_xml2_cmake_normal}")
  message(FATAL_ERROR "SOURCE:xml2-noncanonical-host-module-root")
endif()
set(_foundation_xml2_thread_module "${_foundation_xml2_cmake_normal}/Modules/FindThreads.cmake")
cmake_path(NORMAL_PATH _foundation_xml2_thread_module OUTPUT_VARIABLE _foundation_xml2_module_normal)
cmake_path(IS_PREFIX _foundation_xml2_host_normal "${_foundation_xml2_cmake_normal}" NORMALIZE _foundation_xml2_cmake_inside)
cmake_path(IS_PREFIX _foundation_xml2_host_normal "${_foundation_xml2_module_normal}" NORMALIZE _foundation_xml2_module_inside)
if(NOT _foundation_xml2_cmake_inside OR NOT _foundation_xml2_module_inside OR
   NOT "${_foundation_xml2_thread_module}" STREQUAL "${_foundation_xml2_module_normal}" OR
   "${_foundation_xml2_module_normal}" STREQUAL "${_foundation_xml2_host_normal}")
  message(FATAL_ERROR "SOURCE:xml2-thread-module-outside-held-host")
endif()
file(REAL_PATH "${_foundation_xml2_host_normal}" _foundation_xml2_host_real)
file(REAL_PATH "${_foundation_xml2_cmake_normal}" _foundation_xml2_cmake_real)
file(REAL_PATH "${_foundation_xml2_module_normal}" _foundation_xml2_module_real)
if(NOT "${_foundation_xml2_host_real}" STREQUAL "${_foundation_xml2_host_normal}" OR
   NOT "${_foundation_xml2_cmake_real}" STREQUAL "${_foundation_xml2_cmake_normal}" OR
   NOT "${_foundation_xml2_module_real}" STREQUAL "${_foundation_xml2_module_normal}")
  message(FATAL_ERROR "SOURCE:xml2-aliased-host-module-path")
endif()
if(NOT EXISTS "${_foundation_xml2_thread_module}" OR
   IS_DIRECTORY "${_foundation_xml2_thread_module}")
  message(FATAL_ERROR "SOURCE:xml2-cmake-3.31.6-thread-module-unavailable")
endif()
file(SHA256 "${_foundation_xml2_thread_module}" _foundation_xml2_threads_module_sha256)
if(NOT "${_foundation_xml2_threads_module_sha256}" STREQUAL
   "e6612143863d6b726d5797095e1c8cc3216d111a29f9e4563f664413b08506a7")
  message(FATAL_ERROR "SOURCE:xml2-unsupported-thread-module-source")
endif()
function(_foundation_xml2_zero_threads)
  if(NOT TARGET Threads::Threads OR
     NOT "${CMAKE_USE_WIN32_THREADS_INIT}" STREQUAL "1" OR NOT Threads_FOUND)
    message(FATAL_ERROR "SOURCE:xml2-win32-thread-discovery-not-established")
  endif()
  if(NOT "${CMAKE_THREAD_LIBS_INIT}" STREQUAL "" OR
     CMAKE_USE_PTHREADS_INIT OR THREADS_HAVE_PTHREAD_ARG)
    message(FATAL_ERROR "SOURCE:xml2-thread-discovery-has-external-inputs")
  endif()
  get_target_property(_foundation_threads_type Threads::Threads TYPE)
  get_target_property(_foundation_threads_imported Threads::Threads IMPORTED)
  if(NOT "${_foundation_threads_type}" STREQUAL "INTERFACE_LIBRARY" OR
     NOT "${_foundation_threads_imported}" STREQUAL "TRUE")
    message(FATAL_ERROR "SOURCE:xml2-thread-target-shape")
  endif()
  foreach(_foundation_property IN ITEMS
    INTERFACE_LINK_LIBRARIES
    INTERFACE_LINK_LIBRARIES_DIRECT
    INTERFACE_LINK_LIBRARIES_DIRECT_EXCLUDE
    INTERFACE_LINK_OPTIONS
    INTERFACE_LINK_DIRECTORIES
    INTERFACE_COMPILE_OPTIONS
    INTERFACE_COMPILE_DEFINITIONS
    INTERFACE_COMPILE_FEATURES
    INTERFACE_INCLUDE_DIRECTORIES
    INTERFACE_SYSTEM_INCLUDE_DIRECTORIES
    INTERFACE_SOURCES
    INTERFACE_PRECOMPILE_HEADERS
  )
    get_property(_foundation_is_set TARGET Threads::Threads PROPERTY "${_foundation_property}" SET)
    if(_foundation_is_set)
      get_property(_foundation_value TARGET Threads::Threads PROPERTY "${_foundation_property}")
      if(NOT "${_foundation_value}" STREQUAL "")
        message(FATAL_ERROR "SOURCE:xml2-nonempty-thread-interface:${_foundation_property}")
      endif()
    endif()
  endforeach()
endfunction()

if(LIBXML2_WITH_THREADS)
	find_package(Threads REQUIRED MODULE)
	_foundation_xml2_zero_threads()
	set(THREAD_LIBS ${CMAKE_THREAD_LIBS_INIT})
	list(APPEND CMAKE_REQUIRED_LIBRARIES Threads::Threads)
endif()

if(LIBXML2_WITH_ZLIB)
	find_package(ZLIB REQUIRED)
endif()

if (NOT MSVC)
	check_c_source_compiles("
		void __attribute__((destructor))
		f(void) {}
		int main(void) { return 0; }
	" HAVE_ATTRIBUTE_DESTRUCTOR)
	if(HAVE_ATTRIBUTE_DESTRUCTOR)
		set(ATTRIBUTE_DESTRUCTOR "__attribute__((destructor))")
	endif()
	check_include_files(arpa/inet.h HAVE_ARPA_INET_H)
	check_function_exists(class HAVE_CLASS)
	check_include_files(dlfcn.h HAVE_DLFCN_H)
	check_library_exists(dl dlopen "" HAVE_DLOPEN)
	check_include_files(dl.h HAVE_DL_H)
	check_include_files(fcntl.h HAVE_FCNTL_H)
	check_function_exists(fpclass HAVE_FPCLASS)
	check_function_exists(ftime HAVE_FTIME)
	check_function_exists(gettimeofday HAVE_GETTIMEOFDAY)
	check_include_files(inttypes.h HAVE_INTTYPES_H)
	check_function_exists(isascii HAVE_ISASCII)
	check_library_exists(history append_history "" HAVE_LIBHISTORY)
	check_library_exists(readline readline "" HAVE_LIBREADLINE)
	check_function_exists(mmap HAVE_MMAP)
	check_function_exists(munmap HAVE_MUNMAP)
	check_include_files(netdb.h HAVE_NETDB_H)
	check_include_files(netinet/in.h HAVE_NETINET_IN_H)
	check_include_files(poll.h HAVE_POLL_H)
	check_library_exists(dld shl_load "" HAVE_SHLLOAD)
	check_function_exists(stat HAVE_STAT)
	check_include_files(stdint.h HAVE_STDINT_H)
	check_include_files(sys/mman.h HAVE_SYS_MMAN_H)
	check_include_files(sys/select.h HAVE_SYS_SELECT_H)
	check_include_files(sys/socket.h HAVE_SYS_SOCKET_H)
	check_include_files(sys/stat.h HAVE_SYS_STAT_H)
	check_include_files(sys/timeb.h HAVE_SYS_TIMEB_H)
	check_include_files(sys/time.h HAVE_SYS_TIME_H)
	check_include_files(unistd.h HAVE_UNISTD_H)
	check_symbol_exists(va_copy stdarg.h HAVE_VA_COPY)
	check_symbol_exists(__va_copy stdarg.h HAVE___VA_COPY)
	check_c_source_compiles("
		#include <stdarg.h>
		void a(va_list* ap) {};
		int main() { va_list ap1, ap2; a(&ap1); ap2 = (va_list) ap1; return 0; }
	" VA_LIST_IS_ARRAY_TEST)
	if(VA_LIST_IS_ARRAY_TEST)
		set(VA_LIST_IS_ARRAY FALSE)
	else()
		set(VA_LIST_IS_ARRAY TRUE)
	endif()
	check_c_source_compiles("
		#include <stddef.h>
		#include <sys/socket.h>
		int main() { (void) getsockopt(1, 1, 1, NULL, (socklen_t*) NULL); return 0; }
	" XML_SOCKLEN_T_SOCKLEN_T)
	if(XML_SOCKLEN_T_SOCKLEN_T)
		set(XML_SOCKLEN_T socklen_t)
	else()
		check_c_source_compiles("
			#include <stddef.h>
			#include <sys/socket.h>
			int main() { (void) getsockopt(1, 1, 1, NULL, (size_t*) NULL); return 0; }
		" XML_SOCKLEN_T_SIZE_T)
		if(XML_SOCKLEN_T_SIZE_T)
			set(XML_SOCKLEN_T size_t)
		else()
			check_c_source_compiles("
				#include <stddef.h>
				#include <sys/socket.h>
				int main() { (void) getsockopt (1, 1, 1, NULL, (int*) NULL); return 0; }
			" XML_SOCKLEN_T_INT)
			set(XML_SOCKLEN_T int)
		endif()
	endif()
endif()

if(LIBXML2_WITH_TLS)
	check_c_source_compiles(
		"_Thread_local int v; int main(){return 0;}"
		XML_THREAD_LOCAL_C11
	)
	if (XML_THREAD_LOCAL_C11)
		set(XML_THREAD_LOCAL "_Thread_local")
	else()
		check_c_source_compiles(
			"__thread int v; int main(){return 0;}"
			XML_THREAD_LOCAL_THREAD
		)
		if (XML_THREAD_LOCAL_THREAD)
			set(XML_THREAD_LOCAL "__thread")
		else()
			check_c_source_compiles(
				"__declspec(thread) int v; int main(){return 0;}"
				XML_THREAD_LOCAL_DECLSPEC
			)
			if (XML_THREAD_LOCAL_DECLSPEC)
				set(XML_THREAD_LOCAL "__declspec(thread)")
			endif()
		endif()
	endif()
endif()

set(
	LIBXML2_HDRS
	include/libxml/c14n.h
	include/libxml/catalog.h
	include/libxml/chvalid.h
	include/libxml/debugXML.h
	include/libxml/dict.h
	include/libxml/encoding.h
	include/libxml/entities.h
	include/libxml/globals.h
	include/libxml/hash.h
	include/libxml/HTMLparser.h
	include/libxml/HTMLtree.h
	include/libxml/list.h
	include/libxml/nanoftp.h
	include/libxml/nanohttp.h
	include/libxml/parser.h
	include/libxml/parserInternals.h
	include/libxml/pattern.h
	include/libxml/relaxng.h
	include/libxml/SAX.h
	include/libxml/SAX2.h
	include/libxml/schemasInternals.h
	include/libxml/schematron.h
	include/libxml/threads.h
	include/libxml/tree.h
	include/libxml/uri.h
	include/libxml/valid.h
	include/libxml/xinclude.h
	include/libxml/xlink.h
	include/libxml/xmlIO.h
	include/libxml/xmlautomata.h
	include/libxml/xmlerror.h
	include/libxml/xmlexports.h
	include/libxml/xmlmemory.h
	include/libxml/xmlmodule.h
	include/libxml/xmlreader.h
	include/libxml/xmlregexp.h
	include/libxml/xmlsave.h
	include/libxml/xmlschemas.h
	include/libxml/xmlschemastypes.h
	include/libxml/xmlstring.h
	include/libxml/xmlunicode.h
	include/libxml/xmlwriter.h
	include/libxml/xpath.h
	include/libxml/xpathInternals.h
	include/libxml/xpointer.h
)

set(
	LIBXML2_SRCS
	buf.c
	c14n.c
	catalog.c
	chvalid.c
	debugXML.c
	dict.c
	encoding.c
	entities.c
	error.c
	globals.c
	hash.c
	HTMLparser.c
	HTMLtree.c
	legacy.c
	list.c
	nanoftp.c
	nanohttp.c
	parser.c
	parserInternals.c
	pattern.c
	relaxng.c
	SAX.c
	SAX2.c
	schematron.c
	threads.c
	tree.c
	uri.c
	valid.c
	xinclude.c
	xlink.c
	xmlIO.c
	xmlmemory.c
	xmlmodule.c
	xmlreader.c
	xmlregexp.c
	xmlsave.c
	xmlschemas.c
	xmlschemastypes.c
	xmlstring.c
	xmlunicode.c
	xmlwriter.c
	xpath.c
	xpointer.c
	xzlib.c
)

if(WIN32)
	list(APPEND LIBXML2_SRCS win32/libxml2.rc)
	file(
		WRITE
		${CMAKE_CURRENT_BINARY_DIR}/rcVersion.h
		"#define LIBXML_MAJOR_VERSION ${LIBXML_MAJOR_VERSION}\n"
		"#define LIBXML_MINOR_VERSION ${LIBXML_MINOR_VERSION}\n"
		"#define LIBXML_MICRO_VERSION ${LIBXML_MICRO_VERSION}\n"
		"#define LIBXML_DOTTED_VERSION \"${VERSION}\"\n"
	)
endif()

if(LIBXML2_WITH_TRIO)
	list(APPEND LIBXML2_SRCS trio.c triostr.c)
endif()

list(TRANSFORM LIBXML2_HDRS PREPEND "${SOURCE_ROOT}/")
list(TRANSFORM LIBXML2_SRCS PREPEND "${SOURCE_ROOT}/")
add_library(LibXml2 STATIC ${LIBXML2_HDRS} ${LIBXML2_SRCS})
add_library(LibXml2::LibXml2 ALIAS LibXml2)

target_compile_definitions(LibXml2 PRIVATE SYSCONFDIR="${CMAKE_INSTALL_FULL_SYSCONFDIR}")

if(LIBXML2_WITH_THREADS)
	target_compile_definitions(LibXml2 PRIVATE _REENTRANT)
        if(NOT WIN32)
		check_include_files(pthread.h HAVE_PTHREAD_H)
	endif()
endif()

target_include_directories(
	LibXml2
	PUBLIC
	$<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}>
	$<BUILD_INTERFACE:${SOURCE_ROOT}/include>
	$<INSTALL_INTERFACE:$<INSTALL_PREFIX>/${CMAKE_INSTALL_INCLUDEDIR}/libxml2>
)

if(LIBXML2_WITH_MODULES)
	if(HAVE_DLOPEN)
		target_link_libraries(LibXml2 PRIVATE dl)
		set(MODULE_PLATFORM_LIBS "-ldl")
	endif()

	if(HAVE_SHLLOAD)
		target_link_libraries(LibXml2 PRIVATE dld)
		set(MODULE_PLATFORM_LIBS "-ldld")
	endif()
endif()

if(UNIX)
	target_link_libraries(LibXml2 PRIVATE m)
	set(LIBM "-lm")
endif()

if(WIN32)
	target_link_libraries(LibXml2 PRIVATE ws2_32)
	set(WINSOCK_LIBS "-lws2_32")
endif()

if(LIBXML2_WITH_ICONV)
	target_link_libraries(LibXml2 PUBLIC Iconv::Iconv)
	if(NOT Iconv_IS_BUILT_IN)
		set(ICONV_LIBS "-liconv")
	endif()
endif()

if(LIBXML2_WITH_ICU)
	target_link_libraries(LibXml2 PRIVATE ICU::data ICU::i18n ICU::uc)
	if(WIN32)
		set(ICU_LDFLAGS "-licudt -licuin -licuuc")
	else()
		set(ICU_LDFLAGS "-licudata -licui18n -licuuc")
	endif()
	list(APPEND XML_PRIVATE_LIBS "${ICU_LDFLAGS}")
	set(ICU_PC_FOUND FALSE) # Metadata only; never launch pkg-config.
	if(ICU_PC_FOUND)
		list(APPEND XML_PC_REQUIRES icu-i18n)
	else()
		list(APPEND XML_PC_LIBS "${ICU_LDFLAGS}")
	endif()
endif()

if(LIBXML2_WITH_LZMA)
	target_link_libraries(LibXml2 PRIVATE LibLZMA::LibLZMA)
	set(LibLZMA_LDFLAGS "-llzma")
	list(APPEND XML_PRIVATE_LIBS "${LibLZMA_LDFLAGS}")
	set(LibLZMA_PC_FOUND FALSE) # Metadata only; never launch pkg-config.
	if(LibLZMA_PC_FOUND)
		list(APPEND XML_PC_REQUIRES liblzma)
	else()
		list(APPEND XML_PC_LIBS "${LibLZMA_LDFLAGS}")
	endif()
endif()

if(LIBXML2_WITH_THREADS)
	target_link_libraries(LibXml2 PRIVATE Threads::Threads)
endif()

if(LIBXML2_WITH_ZLIB)
	target_link_libraries(LibXml2 PRIVATE ZLIB::ZLIB)
	set(ZLIB_LDFLAGS "-lz")
	list(APPEND XML_PRIVATE_LIBS "${ZLIB_LDFLAGS}")
	set(ZLIB_PC_FOUND FALSE) # Metadata only; never launch pkg-config.
	if(ZLIB_PC_FOUND)
		list(APPEND XML_PC_REQUIRES zlib)
	else()
		list(APPEND XML_PC_LIBS "${ZLIB_LDFLAGS}")
	endif()
endif()

if(CMAKE_C_COMPILER_ID MATCHES "Clang" OR CMAKE_C_COMPILER_ID STREQUAL "GNU")
	# These compiler flags can break the checks above so keep them here.
	set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -pedantic -Wall -Wextra -Wshadow \
-Wpointer-arith -Wcast-align -Wwrite-strings \
-Wstrict-prototypes -Wmissing-prototypes \
-Wno-long-long -Wno-format-extra-args")

	if(BUILD_SHARED_LIBS AND UNIX AND NOT APPLE)
		check_linker_flag(C "LINKER:--undefined-version" FLAG_UNDEFINED_VERSION)
		if (FLAG_UNDEFINED_VERSION)
			target_link_options(LibXml2 PRIVATE "LINKER:--undefined-version")
		endif()
		target_link_options(LibXml2 PRIVATE "LINKER:--version-script=${SOURCE_ROOT}/libxml2.syms")
	endif()
endif()

set_target_properties(
	LibXml2
	PROPERTIES
	IMPORT_PREFIX lib
	OUTPUT_NAME xml2
	POSITION_INDEPENDENT_CODE ON
	PREFIX lib
	VERSION ${PROJECT_VERSION}
        SOVERSION ${LIBXML_MAJOR_VERSION}
)

if(MSVC)
	if(BUILD_SHARED_LIBS)
		set_target_properties(
			LibXml2
			PROPERTIES
			DEBUG_POSTFIX d
		)
	else()
		set_target_properties(
			LibXml2
			PROPERTIES
			DEBUG_POSTFIX sd
			MINSIZEREL_POSTFIX s
			RELEASE_POSTFIX s
			RELWITHDEBINFO_POSTFIX s
		)
	endif()
endif()


# Reviewed Windows configure_file path; source-owned static-only install.
configure_file("${SOURCE_ROOT}/include/win32config.h" config.h COPYONLY)
configure_file("${SOURCE_ROOT}/include/libxml/xmlversion.h.in" libxml/xmlversion.h)
target_compile_definitions(LibXml2 PUBLIC LIBXML_STATIC PRIVATE U_STATIC_IMPLEMENTATION)
set_target_properties(LibXml2 PROPERTIES PREFIX "lib" OUTPUT_NAME "xml2" SUFFIX ".lib" RELEASE_POSTFIX "s" DEBUG_POSTFIX "" MSVC_RUNTIME_LIBRARY "MultiThreaded")
install(TARGETS LibXml2 ARCHIVE DESTINATION lib)
install(FILES ${LIBXML2_HDRS} "${PROJECT_BINARY_DIR}/libxml/xmlversion.h" DESTINATION include/libxml2/libxml)

# Recheck after the complete maintained XML2 target graph has been constructed.
_foundation_xml2_zero_threads()
get_target_property(_foundation_xml2_type LibXml2 TYPE)
get_target_property(_foundation_xml2_links LibXml2 LINK_LIBRARIES)
get_target_property(_foundation_xml2_interface_links LibXml2 INTERFACE_LINK_LIBRARIES)
if(NOT "${_foundation_xml2_type}" STREQUAL "STATIC_LIBRARY" OR
   NOT "${_foundation_xml2_links}" STREQUAL
       "ws2_32;ICU::data;ICU::i18n;ICU::uc;Threads::Threads;ZLIB::ZLIB" OR
   NOT "${_foundation_xml2_interface_links}" STREQUAL
       "$<LINK_ONLY:ws2_32>;$<LINK_ONLY:ICU::data>;$<LINK_ONLY:ICU::i18n>;$<LINK_ONLY:ICU::uc>;$<LINK_ONLY:Threads::Threads>;$<LINK_ONLY:ZLIB::ZLIB>")
  message(FATAL_ERROR "SOURCE:xml2-unreviewed-static-link-interface")
endif()
""",
    'nghttp2-project': r"""# nghttp2 - HTTP/2 C Library
#
# Copyright (c) 2012, 2013, 2014, 2015 Tatsuhiro Tsujikawa
# Copyright (c) 2016 Peter Wu <peter@lekensteyn.nl>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

cmake_minimum_required(VERSION 3.14)
# XXX using 1.8.90 instead of 1.9.0-DEV
project(nghttp2 VERSION 1.64.0 LANGUAGES C)
if(NOT WIN32 OR NOT MSVC OR NOT CMAKE_C_COMPILER_ID STREQUAL "Clang" OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "The fixed graph requires native Windows x86_64 clang-cl")
endif()
if(NOT CMAKE_C_COMPILER_TARGET STREQUAL "x86_64-pc-windows-msvc")
  message(FATAL_ERROR "The fixed graph requires the admitted compiler target")
endif()


# See versioning rule:
#  https://www.gnu.org/software/libtool/manual/html_node/Updating-version-info.html
set(LT_CURRENT  42)
set(LT_REVISION 3)
set(LT_AGE      28)

set(CMAKE_MODULE_PATH "${PROJECT_ROOT}/modules")
include("${SOURCE_ROOT}/cmake/Version.cmake")

math(EXPR LT_SOVERSION "${LT_CURRENT} - ${LT_AGE}")
set(LT_VERSION "${LT_SOVERSION}.${LT_AGE}.${LT_REVISION}")
set(PACKAGE_VERSION     "${PROJECT_VERSION}")
HexVersion(PACKAGE_VERSION_NUM ${PROJECT_VERSION_MAJOR} ${PROJECT_VERSION_MINOR} ${PROJECT_VERSION_PATCH})

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE RelWithDebInfo CACHE STRING "Choose the build type" FORCE)

  # Include "None" as option to disable any additional (optimization) flags,
  # relying on just CMAKE_C_FLAGS and CMAKE_CXX_FLAGS (which are empty by
  # default). These strings are presented in cmake-gui.
  set_property(CACHE CMAKE_BUILD_TYPE PROPERTY STRINGS
    "None" "Debug" "Release" "MinSizeRel" "RelWithDebInfo")
endif()

include(GNUInstallDirs)
include(CMakeDependentOption)

# For documentation
set(Python3_FOUND FALSE)

# Auto-detection of features that can be toggled
if(NOT ENABLE_LIB_ONLY)
  enable_language(CXX)
  # No application dependency discovery.
  # No application dependency discovery.
  # No application dependency discovery.
  # No application dependency discovery.
  # No application dependency discovery.
endif()

if(WITH_WOLFSSL)
  # No application dependency discovery.
else()
  # No application dependency discovery.
endif()
# No application dependency discovery.
if(OPENSSL_FOUND)
  # No application dependency discovery.
  if(LIBNGTCP2_CRYPTO_QUICTLS_FOUND)
    set(HAVE_LIBNGTCP2_CRYPTO_QUICTLS 1)
  endif()
endif()
if(WOLFSSL_FOUND)
  # No application dependency discovery.
  if(LIBNGTCP2_CRYPTO_WOLFSSL_FOUND)
    set(HAVE_LIBNGTCP2_CRYPTO_WOLFSSL 1)
  endif()
endif()
# No application dependency discovery.
if(WITH_LIBBPF)
  # No application dependency discovery.
  if(NOT LIBBPF_FOUND)
    message(FATAL_ERROR "libbpf was requested (WITH_LIBBPF=1) but not found.")
  endif()
endif()
if((OPENSSL_FOUND OR WOLFSSL_FOUND) AND LIBEV_FOUND AND ZLIB_FOUND)
  set(ENABLE_APP_DEFAULT ON)
else()
  set(ENABLE_APP_DEFAULT OFF)
endif()
# No application dependency discovery.
# No application dependency discovery.
set(ENABLE_HPACK_TOOLS_DEFAULT ${JANSSON_FOUND})
# 2.0.8 is required because we use evconnlistener_set_error_cb()
# No application dependency discovery.
set(ENABLE_EXAMPLES_DEFAULT ${LIBEVENT_OPENSSL_FOUND})

# No application dependency discovery.
set(WITH_LIBXML2_DEFAULT    ${LIBXML2_FOUND})
# No application dependency discovery.
set(WITH_JEMALLOC_DEFAULT   ${JEMALLOC_FOUND})

include("${SOURCE_ROOT}/CMakeOptions.txt")

if(ENABLE_LIB_ONLY AND (ENABLE_APP OR ENABLE_HPACK_TOOLS OR ENABLE_EXAMPLES))
  # Remember when disabled options are disabled for later diagnostics.
  set(ENABLE_LIB_ONLY_DISABLED_OTHERS 1)
else()
  set(ENABLE_LIB_ONLY_DISABLED_OTHERS 0)
endif()
if(ENABLE_LIB_ONLY)
  set(ENABLE_APP            OFF)
  set(ENABLE_HPACK_TOOLS    OFF)
  set(ENABLE_EXAMPLES       OFF)
endif()

# Do not disable assertions based on CMAKE_BUILD_TYPE.
foreach(_build_type "Release" "MinSizeRel" "RelWithDebInfo")
  foreach(_lang C CXX)
    string(TOUPPER "CMAKE_${_lang}_FLAGS_${_build_type}" _var)
    string(REGEX REPLACE "(^| )[/-]D *NDEBUG($| )" " " ${_var} "${${_var}}")
  endforeach()
endforeach()

if(CMAKE_C_COMPILER_ID MATCHES "GNU" OR CMAKE_C_COMPILER_ID MATCHES "Clang")
  set(HINT_NORETURN       "__attribute__((noreturn))")
else()
  set(HINT_NORETURN)
endif()

if(NOT ENABLE_LIB_ONLY)
  include(ExtractValidFlags)
  foreach(_cxx1x_flag -std=c++20)
    extract_valid_cxx_flags(_cxx1x_flag_supported ${_cxx1x_flag})
    if(_cxx1x_flag_supported)
      set(CXX1XCXXFLAGS ${_cxx1x_flag})
      break()
    endif()
  endforeach()

  include(CMakePushCheckState)
  include(CheckCXXSourceCompiles)
  cmake_push_check_state()
  set(CMAKE_REQUIRED_DEFINITIONS "${CXX1XCXXFLAGS}")
  # Check that std::future is available.
  check_cxx_source_compiles("
  #include <vector>
  #include <future>
  int main() { std::vector<std::future<int>> v; }" HAVE_STD_FUTURE)
  # Check that std::map::emplace is available for g++-4.7.
  check_cxx_source_compiles("
  #include <map>
  int main() { std::map<int, int>().emplace(1, 2); }" HAVE_STD_MAP_EMPLACE)
  cmake_pop_check_state()
endif()

# Checks for libraries.
# Additional libraries required for programs under src directory.
set(APP_LIBRARIES)

set(CMAKE_THREAD_PREFER_PTHREAD 1)
find_package(Threads)
if(CMAKE_USE_PTHREADS_INIT)
  list(APPEND APP_LIBRARIES ${CMAKE_THREAD_LIBS_INIT})
endif()
# XXX android and C++, is this still needed in cmake?
# case "$host" in
#   *android*)
#     android_build=yes
#     # android does not need -pthread, but needs following 3 libs for C++
#     APPLDFLAGS="$APPLDFLAGS -lstdc++ -latomic -lsupc++"

# dl: openssl requires libdl when it is statically linked.
# XXX shouldn't ${CMAKE_DL_LIBS} be appended to OPENSSL_LIBRARIES instead of
# APP_LIBRARIES if it is really specific to OpenSSL?



# openssl (for src)
include(CheckSymbolExists)
set(HAVE_OPENSSL    ${OPENSSL_FOUND})
if(NOT ENABLE_LIB_ONLY AND OPENSSL_FOUND)
  set(OPENSSL_INCLUDE_DIRS  ${OPENSSL_INCLUDE_DIR})
  cmake_push_check_state()
  set(CMAKE_REQUIRED_INCLUDES   "${OPENSSL_INCLUDE_DIR}")
  set(CMAKE_REQUIRED_LIBRARIES  "${OPENSSL_LIBRARIES}")
  if(WIN32)
    set(CMAKE_REQUIRED_LIBRARIES "${CMAKE_REQUIRED_LIBRARIES}" "ws2_32" "bcrypt")
  endif()
  if(ENABLE_HTTP3)
    check_symbol_exists(SSL_provide_quic_data "openssl/ssl.h" HAVE_SSL_PROVIDE_QUIC_DATA)
    if(NOT HAVE_SSL_PROVIDE_QUIC_DATA)
        message(WARNING "OpenSSL in ${OPENSSL_LIBRARIES} does not have SSL_provide_quic_data.  HTTP/3 support cannot be enabled")
    endif()
  endif()
  cmake_pop_check_state()
else()
  set(OPENSSL_INCLUDE_DIRS  "")
  set(OPENSSL_LIBRARIES     "")
endif()
# wolfSSL (for src)
set(HAVE_WOLFSSL ${WOLFSSL_FOUND})
if(WOLFSSL_FOUND)
  set(WOLFSSL_INCLUDE_DIRS ${WOLFSSL_INCLUDE_DIR})
  cmake_push_check_state()
  set(CMAKE_REQUIRED_INCLUDES   "${WOLFSSL_INCLUDE_DIR}")
  set(CMAKE_REQUIRED_LIBRARIES  "${WOLFSSL_LIBRARIES}")
  check_symbol_exists(SSL_provide_quic_data "wolfssl/options.h;wolfssl/ssl.h" HAVE_WOLFSSL_SSL_PROVIDE_QUIC_DATA)
  if(NOT HAVE_WOLFSSL_SSL_PROVIDE_QUIC_DATA)
    message(WARNING "wolfSSL in ${WOLFSSL_LIBRARIES} does not have SSL_provide_quic_data.  HTTP/3 support cannot be enabled")
  endif()
  cmake_pop_check_state()
else()
  set(WOLFSSL_INCLUDE_DIRS "")
  set(WOLFSSL_LIBRARIES    "")
endif()
# libev (for src)
set(HAVE_LIBEV      ${LIBEV_FOUND})
set(HAVE_ZLIB       ${ZLIB_FOUND})
set(HAVE_SYSTEMD    ${SYSTEMD_FOUND})
set(HAVE_LIBEVENT_OPENSSL ${LIBEVENT_FOUND})
if(LIBEVENT_FOUND)
  # Must both link the core and openssl libraries.
  set(LIBEVENT_OPENSSL_LIBRARIES ${LIBEVENT_LIBRARIES})
endif()
# libc-ares (for src)
set(HAVE_LIBCARES   ${LIBCARES_FOUND})
if(LIBCARES_FOUND)
  set(LIBCARES_INCLUDE_DIRS ${LIBCARES_INCLUDE_DIR})
else()
  set(LIBCARES_INCLUDE_DIRS "")
  set(LIBCARES_LIBRARIES    "")
endif()
# jansson (for src/nghttp, src/deflatehd and src/inflatehd)
set(HAVE_JANSSON    ${JANSSON_FOUND})
# libxml2 (for src/nghttp)
set(HAVE_LIBXML2    ${LIBXML2_FOUND})
if(LIBXML2_FOUND)
  set(LIBXML2_INCLUDE_DIRS  ${LIBXML2_INCLUDE_DIR})
else()
  set(LIBXML2_INCLUDE_DIRS  "")
  set(LIBXML2_LIBRARIES     "")
endif()
# jemalloc
set(HAVE_JEMALLOC   ${JEMALLOC_FOUND})

# libbrotli (for src)
set(HAVE_LIBBROTLIENC ${LIBBROTLIENC_FOUND})
set(HAVE_LIBBROTLIDEC ${LIBBROTLIDEC_FOUND})
if(LIBBROTLIENC_FOUND AND LIBBROTLIDEC_FOUND)
  set(HAVE_LIBBROTLI 1)
endif()

# libbpf (for bpf)
set(HAVE_LIBBPF ${LIBBPF_FOUND})
if(LIBBPF_FOUND)
  set(BPFCFLAGS -Wall -O2 -g)
  if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
    # For Debian/Ubuntu
    set(EXTRABPFCFLAGS -I/usr/include/${CMAKE_SYSTEM_PROCESSOR}-linux-gnu)
  endif()

  check_c_source_compiles("
#include <linux/bpf.h>
int main() { enum bpf_stats_type foo; (void)foo; }" HAVE_BPF_STATS_TYPE)
endif()

# The nghttp, nghttpd and nghttpx under src depend on zlib, OpenSSL and libev
if(ENABLE_APP AND NOT (ZLIB_FOUND AND (OPENSSL_FOUND OR WOLFSSL_FOUND) AND LIBEV_FOUND))
  message(FATAL_ERROR "Applications were requested (ENABLE_APP=1) but dependencies are not met.")
endif()

# HTTP/3 requires libngtcp2 + (quictls/openssl +
# libngtcp2_crypto_quictls or wolfSSL + libngtcp2_crypto_wolfssl) and
# libnghttp3.
if(ENABLE_HTTP3 AND NOT (LIBNGTCP2_FOUND AND LIBNGHTTP3_FOUND AND
      ((HAVE_SSL_PROVIDE_QUIC_DATA AND LIBNGTCP2_CRYPTO_QUICTLS_FOUND) OR
	(HAVE_WOLFSSL_SSL_PROVIDE_QUIC_DATA AND LIBNGTCP2_CRYPTO_WOLFSSL_FOUND))))
  message(FATAL_ERROR "HTTP/3 was requested (ENABLE_HTTP3=1) but dependencies are not met.")
endif()

# HPACK tools requires jansson
if(ENABLE_HPACK_TOOLS AND NOT HAVE_JANSSON)
  message(FATAL_ERROR "HPACK tools were requested (ENABLE_HPACK_TOOLS=1) but dependencies are not met.")
endif()

# examples
if(ENABLE_EXAMPLES AND NOT (OPENSSL_FOUND AND LIBEVENT_OPENSSL_FOUND))
  message(FATAL_ERROR "examples were requested (ENABLE_EXAMPLES=1) but dependencies are not met.")
endif()

# third-party http-parser only be built when needed
if(ENABLE_EXAMPLES OR ENABLE_APP OR ENABLE_HPACK_TOOLS)
  set(ENABLE_THIRD_PARTY 1)
  # mruby (for src/nghttpx)
  set(HAVE_MRUBY      ${WITH_MRUBY})
  set(HAVE_NEVERBLEED ${WITH_NEVERBLEED})
else()
  set(HAVE_MRUBY 0)
  set(HAVE_NEVERBLEED 0)
endif()

# Checks for header files.
include(CheckIncludeFile)
check_include_file("arpa/inet.h"    HAVE_ARPA_INET_H)
check_include_file("fcntl.h"        HAVE_FCNTL_H)
check_include_file("inttypes.h"     HAVE_INTTYPES_H)
check_include_file("limits.h"       HAVE_LIMITS_H)
check_include_file("netdb.h"        HAVE_NETDB_H)
check_include_file("netinet/in.h"   HAVE_NETINET_IN_H)
check_include_file("netinet/ip.h"   HAVE_NETINET_IP_H)
check_include_file("pwd.h"          HAVE_PWD_H)
check_include_file("sys/socket.h"   HAVE_SYS_SOCKET_H)
check_include_file("sys/time.h"     HAVE_SYS_TIME_H)
check_include_file("syslog.h"       HAVE_SYSLOG_H)
check_include_file("unistd.h"       HAVE_UNISTD_H)
check_include_file("windows.h"      HAVE_WINDOWS_H)

include(CheckTypeSize)
# Checks for typedefs, structures, and compiler characteristics.
# AC_TYPE_SIZE_T
check_type_size("ssize_t" SIZEOF_SSIZE_T)
if(SIZEOF_SSIZE_T STREQUAL "")
  # ssize_t is a signed type in POSIX storing at least -1.
  # Set it to "int" to match the behavior of AC_TYPE_SSIZE_T (autotools).
  set(ssize_t int)
endif()
# AC_TYPE_UINT8_T
# AC_TYPE_UINT16_T
# AC_TYPE_UINT32_T
# AC_TYPE_UINT64_T
# AC_TYPE_INT8_T
# AC_TYPE_INT16_T
# AC_TYPE_INT32_T
# AC_TYPE_INT64_T
# AC_TYPE_OFF_T
# AC_TYPE_PID_T
# AC_TYPE_UID_T
# XXX To support inline for crappy compilers, see https://cmake.org/Wiki/CMakeTestInline
# AC_C_INLINE
# XXX is AC_SYS_LARGEFILE still needed for modern systems?
# add_definitions(-D_FILE_OFFSET_BITS=64)

include(CheckStructHasMember)
check_struct_has_member("struct tm" tm_gmtoff time.h HAVE_STRUCT_TM_TM_GMTOFF)

# Checks for library functions.
include(CheckFunctionExists)
check_function_exists(_Exit     HAVE__EXIT)
check_function_exists(accept4   HAVE_ACCEPT4)
check_function_exists(clock_gettime HAVE_CLOCK_GETTIME)
check_function_exists(mkostemp  HAVE_MKOSTEMP)
check_function_exists(pipe2     HAVE_PIPE2)

check_symbol_exists(GetTickCount64 sysinfoapi.h HAVE_GETTICKCOUNT64)

include(CheckSymbolExists)
# XXX does this correctly detect initgroups (un)availability on cygwin?
check_symbol_exists(initgroups grp.h HAVE_DECL_INITGROUPS)
if(NOT HAVE_DECL_INITGROUPS AND HAVE_UNISTD_H)
  # FreeBSD declares initgroups() in unistd.h
  check_symbol_exists(initgroups unistd.h HAVE_DECL_INITGROUPS2)
  if(HAVE_DECL_INITGROUPS2)
    set(HAVE_DECL_INITGROUPS 1)
  endif()
endif()

check_symbol_exists(CLOCK_MONOTONIC "time.h" HAVE_DECL_CLOCK_MONOTONIC)

set(WARNCFLAGS)
set(WARNCXXFLAGS)
if(CMAKE_C_COMPILER_ID MATCHES "MSVC")
  if(ENABLE_WERROR)
    set(WARNCFLAGS    /WX)
    set(WARNCXXFLAGS  /WX)
  endif()
else()
  if(ENABLE_WERROR)
    set(WARNCFLAGS   "-Werror")
    set(WARNCXXFLAGS "-Werror")
  endif()

  # Supplier warning modules omitted; no unknown CMake include.
endif()

if(ENABLE_STATIC_CRT)
  foreach(lang C CXX)
    foreach(suffix "" _DEBUG _MINSIZEREL _RELEASE _RELWITHDEBINFO)
      set(var "CMAKE_${lang}_FLAGS${suffix}")
      string(REPLACE "/MD" "/MT" ${var} "${${var}}")
    endforeach()
  endforeach()
endif()

if(ENABLE_DEBUG)
  set(DEBUGBUILD 1)
endif()

# Some platform does not have working std::future.  We disable
# threading for those platforms.
if(NOT ENABLE_THREADS OR NOT HAVE_STD_FUTURE)
  set(NOTHREADS 1)
endif()

add_definitions(-DHAVE_CONFIG_H)
configure_file("${SOURCE_ROOT}/cmakeconfig.h.in" config.h)
# autotools-compatible names
# Sphinx expects relative paths in the .rst files. Use the fact that the files
# below are all one directory level deep.
file(RELATIVE_PATH top_srcdir   "${CMAKE_CURRENT_BINARY_DIR}/dir" "${SOURCE_ROOT}")
file(RELATIVE_PATH top_builddir "${CMAKE_CURRENT_BINARY_DIR}/dir" "${CMAKE_CURRENT_BINARY_DIR}")
set(abs_top_srcdir  "${SOURCE_ROOT}")
set(abs_top_builddir "${CMAKE_CURRENT_BINARY_DIR}")
# libnghttp2.pc (pkg-config file)
set(prefix          "${CMAKE_INSTALL_PREFIX}")
set(exec_prefix     "${CMAKE_INSTALL_PREFIX}")
set(libdir          "${CMAKE_INSTALL_FULL_LIBDIR}")
set(includedir      "${CMAKE_INSTALL_FULL_INCLUDEDIR}")
set(VERSION         "${PACKAGE_VERSION}")
# For init scripts and systemd service file (in contrib/)
set(bindir          "${CMAKE_INSTALL_FULL_BINDIR}")
set(sbindir         "${CMAKE_INSTALL_FULL_SBINDIR}")
file(MAKE_DIRECTORY "${PROJECT_BINARY_DIR}/lib/includes/nghttp2")
configure_file("${SOURCE_ROOT}/lib/includes/nghttp2/nghttp2ver.h.in" "${PROJECT_BINARY_DIR}/lib/includes/nghttp2/nghttp2ver.h" @ONLY)

if(APPLE)
  add_definitions(-D__APPLE_USE_RFC_3542)
endif()

include_directories(
  "${CMAKE_CURRENT_BINARY_DIR}" # for config.h
)
# For use in src/CMakeLists.txt
set(PKGDATADIR "${CMAKE_INSTALL_FULL_DATADIR}/${CMAKE_PROJECT_NAME}")
set(PKGLIBDIR "${CMAKE_INSTALL_FULL_LIBDIR}/${CMAKE_PROJECT_NAME}")


set(NGHTTP2_SOURCES
  "${SOURCE_ROOT}/lib/nghttp2_pq.c"
  "${SOURCE_ROOT}/lib/nghttp2_map.c"
  "${SOURCE_ROOT}/lib/nghttp2_queue.c"
  "${SOURCE_ROOT}/lib/nghttp2_frame.c"
  "${SOURCE_ROOT}/lib/nghttp2_buf.c"
  "${SOURCE_ROOT}/lib/nghttp2_stream.c"
  "${SOURCE_ROOT}/lib/nghttp2_outbound_item.c"
  "${SOURCE_ROOT}/lib/nghttp2_session.c"
  "${SOURCE_ROOT}/lib/nghttp2_submit.c"
  "${SOURCE_ROOT}/lib/nghttp2_helper.c"
  "${SOURCE_ROOT}/lib/nghttp2_alpn.c"
  "${SOURCE_ROOT}/lib/nghttp2_hd.c"
  "${SOURCE_ROOT}/lib/nghttp2_hd_huffman.c"
  "${SOURCE_ROOT}/lib/nghttp2_hd_huffman_data.c"
  "${SOURCE_ROOT}/lib/nghttp2_version.c"
  "${SOURCE_ROOT}/lib/nghttp2_priority_spec.c"
  "${SOURCE_ROOT}/lib/nghttp2_option.c"
  "${SOURCE_ROOT}/lib/nghttp2_callbacks.c"
  "${SOURCE_ROOT}/lib/nghttp2_mem.c"
  "${SOURCE_ROOT}/lib/nghttp2_http.c"
  "${SOURCE_ROOT}/lib/nghttp2_rcbuf.c"
  "${SOURCE_ROOT}/lib/nghttp2_extpri.c"
  "${SOURCE_ROOT}/lib/nghttp2_ratelim.c"
  "${SOURCE_ROOT}/lib/nghttp2_time.c"
  "${SOURCE_ROOT}/lib/nghttp2_debug.c"
  "${SOURCE_ROOT}/lib/sfparse.c"
)
add_library(nghttp2_static STATIC ${NGHTTP2_SOURCES})
target_include_directories(nghttp2_static PRIVATE "${SOURCE_ROOT}/lib/includes" "${PROJECT_BINARY_DIR}/lib/includes")
target_compile_definitions(nghttp2_static PRIVATE BUILDING_NGHTTP2 PUBLIC NGHTTP2_STATICLIB)
set_target_properties(nghttp2_static PROPERTIES PREFIX "" OUTPUT_NAME "nghttp2" SUFFIX ".lib" DEBUG_POSTFIX "" MSVC_RUNTIME_LIBRARY "MultiThreaded")
install(TARGETS nghttp2_static ARCHIVE DESTINATION lib)
install(FILES "${SOURCE_ROOT}/lib/includes/nghttp2/nghttp2.h" "${PROJECT_BINARY_DIR}/lib/includes/nghttp2/nghttp2ver.h" DESTINATION include/nghttp2)
""",
    'curl-configuration-1': r"""cmake_minimum_required(VERSION 3.7...3.16 FATAL_ERROR)
message(STATUS "Using CMake version ${CMAKE_VERSION}")

# Collect command-line arguments for buildinfo.txt.
# Must reside at the top of the script to work as expected.
set(_cmake_args "")
if(NOT "$ENV{CURL_BUILDINFO}$ENV{CURL_CI}$ENV{CI}" STREQUAL "")
  get_cmake_property(_cache_vars CACHE_VARIABLES)
  foreach(_cache_var IN ITEMS ${_cache_vars})
    get_property(_cache_var_helpstring CACHE ${_cache_var} PROPERTY HELPSTRING)
    if(_cache_var_helpstring STREQUAL "No help, variable specified on the command line.")
      get_property(_cache_var_type CACHE ${_cache_var} PROPERTY TYPE)
      get_property(_cache_var_value CACHE ${_cache_var} PROPERTY VALUE)
      if(_cache_var_type STREQUAL "UNINITIALIZED")
        set(_cache_var_type)
      else()
        set(_cache_var_type ":${_cache_var_type}")
      endif()
      string(APPEND _cmake_args " -D${_cache_var}${_cache_var_type}=\"${_cache_var_value}\"")
    endif()
  endforeach()
endif()

set(CMAKE_MODULE_PATH "${PROJECT_ROOT}/modules")
function(curl_count_true _output_count_var)
  set(_count 0)
  foreach(_option_var IN LISTS ARGN)
    if(${_option_var})
      math(EXPR _count "${_count} + 1")
    endif()
  endforeach()
  set(${_output_count_var} ${_count} PARENT_SCOPE)
endfunction()
include("${PROJECT_ROOT}/macros.cmake")
include(CMakeDependentOption)
include(CheckCCompilerFlag)

file(STRINGS "${SOURCE_ROOT}/include/curl/curlver.h" _curl_version_h_contents REGEX "#define LIBCURL_VERSION( |_NUM )")
string(REGEX MATCH "#define LIBCURL_VERSION \"[^\"]*" _curl_version ${_curl_version_h_contents})
string(REGEX REPLACE "[^\"]+\"" "" _curl_version ${_curl_version})
string(REGEX MATCH "#define LIBCURL_VERSION_NUM 0x[0-9a-fA-F]+" _curl_version_num ${_curl_version_h_contents})
string(REGEX REPLACE "[^0]+0x" "" _curl_version_num ${_curl_version_num})
unset(_curl_version_h_contents)

message(STATUS "curl version=[${_curl_version}]")

string(REGEX REPLACE "([0-9]+\.[0-9]+\.[0-9]+).+" "\\1" _curl_version_sem "${_curl_version}")
project(CURL
  VERSION "${_curl_version_sem}"
  LANGUAGES C)
if(NOT WIN32 OR NOT MSVC OR NOT CMAKE_C_COMPILER_ID STREQUAL "Clang" OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "The fixed graph requires native Windows x86_64 clang-cl")
endif()
if(NOT CMAKE_C_COMPILER_TARGET STREQUAL "x86_64-pc-windows-msvc")
  message(FATAL_ERROR "The fixed graph requires the admitted compiler target")
endif()


# CMake does not recognize some targets accurately. Touch up configuration manually as a workaround.
if(WINDOWS_STORE AND MINGW)  # mingw UWP build
  # CMake (as of v3.31.2) gets confused and applies the MSVC rc.exe command-line
  # template to windres. Reset it to the windres template via 'Modules/Platform/Windows-windres.cmake':
  set(CMAKE_RC_COMPILE_OBJECT "<CMAKE_RC_COMPILER> -O coff <DEFINES> <INCLUDES> <FLAGS> <SOURCE> <OBJECT>")
elseif(WIN32 AND WINCE AND CMAKE_C_COMPILER_ID STREQUAL "GNU")  # mingw32ce build
  if(NOT MINGW32CE_LIBRARY_DIR)
    message(FATAL_ERROR "Set MINGW32CE_LIBRARY_DIR variable to the mingw32ce platform library directory.")
  endif()

  set(MINGW 1)
  set(MINGW32CE 1)

  # Build implib with libcurl DLL. Copied from CMake's 'Modules/Platform/Windows-GNU.cmake'.
  set(CMAKE_C_CREATE_SHARED_LIBRARY "<CMAKE_C_COMPILER> <CMAKE_SHARED_LIBRARY_C_FLAGS> <LANGUAGE_COMPILE_FLAGS> <LINK_FLAGS>")
  string(APPEND CMAKE_C_CREATE_SHARED_LIBRARY " <CMAKE_SHARED_LIBRARY_CREATE_C_FLAGS> -o <TARGET> -Wl,--out-implib,<TARGET_IMPLIB>")
  string(APPEND CMAKE_C_CREATE_SHARED_LIBRARY " ${CMAKE_GNULD_IMAGE_VERSION} <OBJECTS> <LINK_LIBRARIES>")

  # Build resources. Copied from CMake's 'Modules/Platform/Windows-windres.cmake'.
  set(CMAKE_RC_COMPILE_OBJECT "<CMAKE_RC_COMPILER> -O coff <DEFINES> <INCLUDES> <FLAGS> <SOURCE> <OBJECT>")
  enable_language(RC)

  # To compile long long integer literals
  set_property(DIRECTORY APPEND PROPERTY COMPILE_OPTIONS "-std=gnu99")
  string(APPEND CMAKE_REQUIRED_FLAGS " -std=gnu99")

  set(CMAKE_C_COMPILE_OPTIONS_PIC "")  # CMake sets it to '-fPIC', confusing the toolchain and breaking builds. Zap it.

  set(CMAKE_STATIC_LIBRARY_PREFIX "lib")
  set(CMAKE_STATIC_LIBRARY_SUFFIX ".a")
  set(CMAKE_SHARED_LIBRARY_PREFIX "lib")
  set(CMAKE_SHARED_LIBRARY_SUFFIX ".dll")
  set(CMAKE_IMPORT_LIBRARY_PREFIX "lib")
  set(CMAKE_IMPORT_LIBRARY_SUFFIX ".dll.a")
  set(CMAKE_FIND_LIBRARY_PREFIXES "lib" "")
  set(CMAKE_FIND_LIBRARY_SUFFIXES ".dll.a" ".a" ".lib")
elseif(DOS AND CMAKE_C_COMPILER_ID STREQUAL "GNU")  # DJGPP
  set(CMAKE_STATIC_LIBRARY_PREFIX "lib")
  set(CMAKE_STATIC_LIBRARY_SUFFIX ".a")
  set(CMAKE_FIND_LIBRARY_PREFIXES "lib")
  set(CMAKE_FIND_LIBRARY_SUFFIXES ".a")
endif()

# Fill platform level variable when using CMake's built-in Android configuration
if(ANDROID AND NOT DEFINED ANDROID_PLATFORM_LEVEL AND NOT CMAKE_SYSTEM_VERSION EQUAL 1)
  set(ANDROID_PLATFORM_LEVEL "${CMAKE_SYSTEM_VERSION}")
endif()

set(_target_flags "")
if(APPLE)
  string(APPEND _target_flags " APPLE")
endif()
if(UNIX)
  string(APPEND _target_flags " UNIX")
endif()
if(BSD)
  string(APPEND _target_flags " BSD")
endif()
if(ANDROID)
  string(APPEND _target_flags " ANDROID-${ANDROID_PLATFORM_LEVEL}")
endif()
if(WIN32)
  string(APPEND _target_flags " WIN32")
endif()
if(WINCE)
  string(APPEND _target_flags " WINCE")
endif()
if(WINDOWS_STORE)
  string(APPEND _target_flags " UWP")
endif()
if(CYGWIN)
  string(APPEND _target_flags " CYGWIN")
endif()
if(DOS)
  string(APPEND _target_flags " DOS")
endif()
if(AMIGA)
  string(APPEND _target_flags " AMIGA")
endif()
if(CMAKE_C_COMPILER_ID STREQUAL "GNU")
  string(APPEND _target_flags " GCC")
endif()
if(CMAKE_C_COMPILER_ID STREQUAL "AppleClang")
  string(APPEND _target_flags " APPLE-CLANG")
elseif(CMAKE_C_COMPILER_ID STREQUAL "Clang" AND MSVC)
  string(APPEND _target_flags " CLANG-CL")
elseif(CMAKE_C_COMPILER_ID MATCHES "Clang")
  string(APPEND _target_flags " LLVM-CLANG")
endif()
if(MINGW)
  string(APPEND _target_flags " MINGW")
endif()
if(MSVC)
  string(APPEND _target_flags " MSVC-${MSVC_VERSION}")
endif()
if(VCPKG_TOOLCHAIN)
  string(APPEND _target_flags " VCPKG")
endif()
if(CMAKE_CROSSCOMPILING)
  string(APPEND _target_flags " CROSS")
endif()
message(STATUS "CMake platform flags:${_target_flags}")

if(CMAKE_CROSSCOMPILING)
  message(STATUS "Cross-compiling: "
    "${CMAKE_HOST_SYSTEM_NAME}/${CMAKE_HOST_SYSTEM_PROCESSOR} -> "
    "${CMAKE_SYSTEM_NAME}/${CMAKE_SYSTEM_PROCESSOR}")
endif()

if(CMAKE_C_COMPILER_TARGET)
  set(CURL_OS "\"${CMAKE_C_COMPILER_TARGET}\"")
else()
  set(CURL_OS "\"${CMAKE_SYSTEM_NAME}\"")
endif()

set(LIB_NAME "libcurl")
set(EXE_NAME "curl")

set_property(DIRECTORY APPEND PROPERTY INCLUDE_DIRECTORIES "${SOURCE_ROOT}/include")

if(NOT DEFINED CMAKE_UNITY_BUILD_BATCH_SIZE)
  set(CMAKE_UNITY_BUILD_BATCH_SIZE 0)
endif()

# Having CMAKE_TRY_COMPILE_TARGET_TYPE set to STATIC_LIBRARY breaks certain
# 'check_function_exists()' detections (possibly more), by detecting
# non-existing features. This happens by default when using 'ios.toolchain.cmake'.
# Work it around by setting this value to `EXECUTABLE`.
if(CMAKE_TRY_COMPILE_TARGET_TYPE STREQUAL "STATIC_LIBRARY")
  message(STATUS "CMAKE_TRY_COMPILE_TARGET_TYPE was found set to STATIC_LIBRARY. "
    "Overriding with EXECUTABLE for feature detections to work.")
  set(_cmake_try_compile_target_type_save ${CMAKE_TRY_COMPILE_TARGET_TYPE})
  set(CMAKE_TRY_COMPILE_TARGET_TYPE "EXECUTABLE")
endif()

option(CURL_WERROR "Turn compiler warnings into errors" OFF)
option(PICKY_COMPILER "Enable picky compiler options" ON)
option(BUILD_CURL_EXE "Build curl executable" ON)
option(BUILD_SHARED_LIBS "Build shared libraries" ON)
option(BUILD_STATIC_LIBS "Build static libraries" OFF)
option(BUILD_STATIC_CURL "Build curl executable with static libcurl" OFF)
option(ENABLE_ARES "Enable c-ares support" OFF)
option(CURL_DISABLE_INSTALL "Disable installation targets" OFF)

if(WIN32)
  option(ENABLE_UNICODE "Use the Unicode version of the Windows API functions" OFF)
  if(WINDOWS_STORE OR WINCE)
    set(ENABLE_UNICODE ON)
  endif()
  if(ENABLE_UNICODE)
    set_property(DIRECTORY APPEND PROPERTY COMPILE_DEFINITIONS "UNICODE" "_UNICODE")
    if(MINGW AND NOT MINGW32CE)
      set_property(DIRECTORY APPEND PROPERTY COMPILE_OPTIONS "-municode")
    endif()
  endif()

  # Apply to all feature checks
  list(APPEND CMAKE_REQUIRED_DEFINITIONS "-DWIN32_LEAN_AND_MEAN")
  if(MSVC)
    list(APPEND CMAKE_REQUIRED_DEFINITIONS "-D_CRT_NONSTDC_NO_DEPRECATE")  # for strdup() detection
  endif()

  set(CURL_TARGET_WINDOWS_VERSION "" CACHE STRING "Minimum target Windows version as hex string")
  if(CURL_TARGET_WINDOWS_VERSION)
    set_property(DIRECTORY APPEND PROPERTY COMPILE_DEFINITIONS "_WIN32_WINNT=${CURL_TARGET_WINDOWS_VERSION}")
    list(APPEND CMAKE_REQUIRED_DEFINITIONS "-D_WIN32_WINNT=${CURL_TARGET_WINDOWS_VERSION}")  # Apply to all feature checks
  endif()

  # Detect actual value of _WIN32_WINNT and store as HAVE_WIN32_WINNT
  curl_internal_test(HAVE_WIN32_WINNT)
  if(HAVE_WIN32_WINNT)
    string(REGEX MATCH "_WIN32_WINNT=0x[0-9a-fA-F]+" CURL_TEST_OUTPUT "${CURL_TEST_OUTPUT}")
    string(REGEX REPLACE "_WIN32_WINNT=" "" CURL_TEST_OUTPUT "${CURL_TEST_OUTPUT}")
    string(REGEX REPLACE "0x([0-9a-f][0-9a-f][0-9a-f])$" "0x0\\1" CURL_TEST_OUTPUT "${CURL_TEST_OUTPUT}")  # pad to 4 digits
    string(TOLOWER "${CURL_TEST_OUTPUT}" HAVE_WIN32_WINNT)
    message(STATUS "Found _WIN32_WINNT=${HAVE_WIN32_WINNT}")
  endif()
  unset(HAVE_WIN32_WINNT CACHE)  # Avoid storing in CMake cache

  if(MINGW)
    # Detect __MINGW64_VERSION_MAJOR, __MINGW64_VERSION_MINOR and store as MINGW64_VERSION
    curl_internal_test(MINGW64_VERSION)
    if(MINGW64_VERSION)
      string(REGEX MATCH "MINGW64_VERSION=[0-9]+\.[0-9]+" CURL_TEST_OUTPUT "${CURL_TEST_OUTPUT}")
      string(REGEX REPLACE "MINGW64_VERSION=" "" MINGW64_VERSION "${CURL_TEST_OUTPUT}")
      if(MINGW64_VERSION)
        message(STATUS "Found MINGW64_VERSION=${MINGW64_VERSION}")
        if(MINGW64_VERSION VERSION_LESS 3.0)
          message(FATAL_ERROR "mingw-w64 3.0 or upper is required")
        endif()
      endif()
    endif()
    unset(MINGW64_VERSION CACHE)  # Avoid storing in CMake cache
  endif()
elseif(DOS OR AMIGA)
  set(BUILD_SHARED_LIBS OFF)
  set(BUILD_STATIC_LIBS ON)
endif()
option(CURL_LTO "Enable compiler Link Time Optimizations" OFF)

if(NOT DOS AND NOT AMIGA)
  # if c-ares is used, default the threaded resolver to OFF
  if(ENABLE_ARES)
    set(_enable_threaded_resolver_default OFF)
  else()
    set(_enable_threaded_resolver_default ON)
  endif()
  option(ENABLE_THREADED_RESOLVER "Enable threaded DNS lookup" ${_enable_threaded_resolver_default})
endif()

# Optional supplier warnings module omitted.

if(CYGWIN OR CMAKE_SYSTEM_NAME STREQUAL "Linux" OR CMAKE_SYSTEM_NAME STREQUAL "GNU")
  set_property(DIRECTORY APPEND PROPERTY COMPILE_DEFINITIONS "_GNU_SOURCE")  # Required for accept4(), pipe2(), sendmmsg()
  list(APPEND CMAKE_REQUIRED_DEFINITIONS "-D_GNU_SOURCE")  # Apply to all feature checks
endif()

option(ENABLE_DEBUG "Enable curl debug features (for developing curl itself)" OFF)
if(ENABLE_DEBUG)
  message(WARNING "This curl build is Debug-enabled and insecure, do not use in production.")
endif()
option(ENABLE_CURLDEBUG "Enable TrackMemory debug feature" ${ENABLE_DEBUG})

set(CURL_DEBUG_MACROS "")
if(ENABLE_DEBUG)
  list(APPEND CURL_DEBUG_MACROS "DEBUGBUILD")
endif()
if(ENABLE_CURLDEBUG)
  list(APPEND CURL_DEBUG_MACROS "CURLDEBUG")
endif()

option(CURL_CLANG_TIDY "Run the build through clang-tidy" OFF)
if(CURL_CLANG_TIDY)
  set(CMAKE_UNITY_BUILD OFF)  # clang-tidy is not looking into #included sources, thus not compatible with unity builds.
  set(_tidy_checks "")
  list(APPEND _tidy_checks "-clang-analyzer-security.insecureAPI.bzero")  # for FD_ZERO() (seen on macOS)
  list(APPEND _tidy_checks "-clang-analyzer-security.insecureAPI.strcpy")
  list(APPEND _tidy_checks "-clang-analyzer-optin.performance.Padding")
  list(APPEND _tidy_checks "-clang-analyzer-security.ArrayBound")  # false positives with clang-tidy v21.1.0
  list(APPEND _tidy_checks "-clang-analyzer-security.insecureAPI.DeprecatedOrUnsafeBufferHandling")
  string(REPLACE ";" "," _tidy_checks "${_tidy_checks}")
  find_program(CLANG_TIDY NAMES "clang-tidy" REQUIRED)
  set(CMAKE_C_CLANG_TIDY "${CLANG_TIDY}" "-checks=${_tidy_checks}" "-quiet")
  unset(_tidy_checks)
  if(CURL_WERROR)
    list(APPEND CMAKE_C_CLANG_TIDY "--warnings-as-errors=*")
  endif()
  if(CURL_CLANG_TIDYFLAGS)
    list(APPEND CMAKE_C_CLANG_TIDY ${CURL_CLANG_TIDYFLAGS})
  endif()
endif()

option(CURL_CODE_COVERAGE "Enable code coverage build options" OFF)
if(CURL_CODE_COVERAGE)
  if(CMAKE_C_COMPILER_ID STREQUAL "GNU")
    set(CURL_COVERAGE_MACROS "NDEBUG")
    set(CURL_COVERAGE_CFLAGS "-O0" "-g" "-fprofile-arcs")
    if(CMAKE_C_COMPILER_VERSION VERSION_GREATER_EQUAL 4.1)
      list(APPEND CURL_COVERAGE_CFLAGS "--coverage")
    else()
      list(APPEND CURL_COVERAGE_CFLAGS "-ftest-coverage")
    endif()
    set(CURL_COVERAGE_LIBS "gcov")
  elseif(CMAKE_C_COMPILER_ID MATCHES "Clang")
    set(CURL_COVERAGE_MACROS "NDEBUG")
    set(CURL_COVERAGE_CFLAGS "-O0" "-g" "-fprofile-instr-generate" "-fcoverage-mapping")
    set(CURL_COVERAGE_LDFLAGS "-fprofile-instr-generate" "-fcoverage-mapping")
  else()
    set(CURL_CODE_COVERAGE OFF)
  endif()
endif()

# For debug libs and exes, add "-d" postfix
if(NOT DEFINED CMAKE_DEBUG_POSTFIX)
  set(CMAKE_DEBUG_POSTFIX "-d")
endif()

set(LIB_STATIC "libcurl_static")
set(LIB_SHARED "libcurl_shared")

if(NOT BUILD_SHARED_LIBS AND NOT BUILD_STATIC_LIBS)
  set(BUILD_STATIC_LIBS ON)
endif()
if(NOT BUILD_STATIC_CURL AND NOT BUILD_SHARED_LIBS)
  set(BUILD_STATIC_CURL ON)
elseif(BUILD_STATIC_CURL AND NOT BUILD_STATIC_LIBS)
  set(BUILD_STATIC_CURL OFF)
endif()

# Lib flavour selected for curl tool
if(BUILD_STATIC_CURL)
  set(LIB_SELECTED_FOR_EXE ${LIB_STATIC})
else()
  set(LIB_SELECTED_FOR_EXE ${LIB_SHARED})
endif()

# Lib flavour selected for example and test programs.
if(BUILD_SHARED_LIBS)
  set(LIB_SELECTED ${LIB_SHARED})
else()
  set(LIB_SELECTED ${LIB_STATIC})
endif()

if(WIN32)
  option(CURL_STATIC_CRT "Build libcurl with static CRT with MSVC (/MT)" OFF)
  if(CURL_STATIC_CRT AND MSVC)
    if(MSVC_VERSION GREATER_EQUAL 1900 OR BUILD_STATIC_CURL OR NOT BUILD_CURL_EXE)
      set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
      set_property(DIRECTORY APPEND PROPERTY COMPILE_OPTIONS "$<$<CONFIG:Release>:-MT>")
      set_property(DIRECTORY APPEND PROPERTY COMPILE_OPTIONS "$<$<CONFIG:Debug>:-MTd>")
    else()
      message(WARNING "Static CRT requires UCRT, static libcurl or no curl executable.")
    endif()
  endif()
endif()

# Override to force-disable or force-enable the use of pkg-config.
if((UNIX AND NOT ANDROID AND (NOT APPLE OR CMAKE_SYSTEM_NAME STREQUAL "Darwin")) OR
   VCPKG_TOOLCHAIN OR
   (MINGW AND NOT CMAKE_CROSSCOMPILING))
  set(_curl_use_pkgconfig_default ON)
else()
  set(_curl_use_pkgconfig_default OFF)
endif()
option(CURL_USE_PKGCONFIG "Enable pkg-config to detect dependencies" ${_curl_use_pkgconfig_default})

# Initialize variables collecting dependency libs, paths, pkg-config names.
set(CURL_NETWORK_AND_TIME_LIBS "")
set(CURL_LIBS "")
set(CURL_LIBDIRS "")
set(LIBCURL_PC_REQUIRES_PRIVATE "")

if(ENABLE_ARES)
  set(USE_ARES 1)
  find_package(Cares REQUIRED)
  list(APPEND CURL_LIBS ${CARES_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${CARES_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${CARES_PC_REQUIRES})
  include_directories(SYSTEM ${CARES_INCLUDE_DIRS})
  link_directories(${CARES_LIBRARY_DIRS})
  if(CARES_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${CARES_CFLAGS}")
  endif()
endif()

set(CURL_HIDES_PRIVATE_SYMBOLS FALSE) # Static archive; no supplier module.

option(CURL_ENABLE_EXPORT_TARGET "Enable CMake export target" ON)
mark_as_advanced(CURL_ENABLE_EXPORT_TARGET)

option(CURL_DISABLE_ALTSVC "Disable alt-svc support" OFF)
mark_as_advanced(CURL_DISABLE_ALTSVC)
option(CURL_DISABLE_SRP "Disable TLS-SRP support" OFF)
mark_as_advanced(CURL_DISABLE_SRP)
option(CURL_DISABLE_COOKIES "Disable cookies support" OFF)
mark_as_advanced(CURL_DISABLE_COOKIES)
option(CURL_DISABLE_BASIC_AUTH "Disable Basic authentication" OFF)
mark_as_advanced(CURL_DISABLE_BASIC_AUTH)
option(CURL_DISABLE_BEARER_AUTH "Disable Bearer authentication" OFF)
mark_as_advanced(CURL_DISABLE_BEARER_AUTH)
option(CURL_DISABLE_DIGEST_AUTH "Disable Digest authentication" OFF)
mark_as_advanced(CURL_DISABLE_DIGEST_AUTH)
option(CURL_DISABLE_KERBEROS_AUTH "Disable Kerberos authentication" OFF)
mark_as_advanced(CURL_DISABLE_KERBEROS_AUTH)
option(CURL_DISABLE_NEGOTIATE_AUTH "Disable negotiate authentication" OFF)
mark_as_advanced(CURL_DISABLE_NEGOTIATE_AUTH)
option(CURL_DISABLE_AWS "Disable aws-sigv4" OFF)
mark_as_advanced(CURL_DISABLE_AWS)
option(CURL_DISABLE_DICT "Disable DICT" OFF)
mark_as_advanced(CURL_DISABLE_DICT)
option(CURL_DISABLE_DOH "Disable DNS-over-HTTPS" OFF)
mark_as_advanced(CURL_DISABLE_DOH)
option(CURL_DISABLE_FILE "Disable FILE" OFF)
mark_as_advanced(CURL_DISABLE_FILE)
option(CURL_DISABLE_FTP "Disable FTP" OFF)
mark_as_advanced(CURL_DISABLE_FTP)
option(CURL_DISABLE_GETOPTIONS "Disable curl_easy_options API for existing options to curl_easy_setopt" OFF)
mark_as_advanced(CURL_DISABLE_GETOPTIONS)
option(CURL_DISABLE_GOPHER "Disable Gopher" OFF)
mark_as_advanced(CURL_DISABLE_GOPHER)
option(CURL_DISABLE_HEADERS_API "Disable headers-api support" OFF)
mark_as_advanced(CURL_DISABLE_HEADERS_API)
option(CURL_DISABLE_HSTS "Disable HSTS support" OFF)
mark_as_advanced(CURL_DISABLE_HSTS)
option(CURL_DISABLE_HTTP "Disable HTTP" OFF)
mark_as_advanced(CURL_DISABLE_HTTP)
option(CURL_DISABLE_HTTP_AUTH "Disable all HTTP authentication methods" OFF)
mark_as_advanced(CURL_DISABLE_HTTP_AUTH)
option(CURL_DISABLE_IMAP "Disable IMAP" OFF)
mark_as_advanced(CURL_DISABLE_IMAP)
option(CURL_DISABLE_LDAP "Disable LDAP" OFF)
mark_as_advanced(CURL_DISABLE_LDAP)
option(CURL_DISABLE_LDAPS "Disable LDAPS" ${CURL_DISABLE_LDAP})
mark_as_advanced(CURL_DISABLE_LDAPS)
option(CURL_DISABLE_LIBCURL_OPTION "Disable --libcurl option from the curl tool" OFF)
mark_as_advanced(CURL_DISABLE_LIBCURL_OPTION)
option(CURL_DISABLE_MIME "Disable MIME support" OFF)
mark_as_advanced(CURL_DISABLE_MIME)
cmake_dependent_option(CURL_DISABLE_FORM_API "Disable form-api"
  OFF "NOT CURL_DISABLE_MIME"
  ON)
mark_as_advanced(CURL_DISABLE_FORM_API)
option(CURL_DISABLE_MQTT "Disable MQTT" OFF)
mark_as_advanced(CURL_DISABLE_MQTT)
option(CURL_DISABLE_BINDLOCAL "Disable local binding support" OFF)
mark_as_advanced(CURL_DISABLE_BINDLOCAL)
option(CURL_DISABLE_NETRC "Disable netrc parser" OFF)
mark_as_advanced(CURL_DISABLE_NETRC)
option(CURL_DISABLE_NTLM "Disable NTLM support" OFF)
mark_as_advanced(CURL_DISABLE_NTLM)
option(CURL_DISABLE_PARSEDATE "Disable date parsing" OFF)
mark_as_advanced(CURL_DISABLE_PARSEDATE)
option(CURL_DISABLE_POP3 "Disable POP3" OFF)
mark_as_advanced(CURL_DISABLE_POP3)
option(CURL_DISABLE_PROGRESS_METER "Disable built-in progress meter" OFF)
mark_as_advanced(CURL_DISABLE_PROGRESS_METER)
option(CURL_DISABLE_PROXY "Disable proxy support" OFF)
mark_as_advanced(CURL_DISABLE_PROXY)
option(CURL_DISABLE_IPFS "Disable IPFS" OFF)
mark_as_advanced(CURL_DISABLE_IPFS)
option(CURL_DISABLE_RTSP "Disable RTSP" OFF)
mark_as_advanced(CURL_DISABLE_RTSP)
option(CURL_DISABLE_SHA512_256 "Disable SHA-512/256 hash algorithm" OFF)
mark_as_advanced(CURL_DISABLE_SHA512_256)
option(CURL_DISABLE_SHUFFLE_DNS "Disable shuffle DNS feature" OFF)
mark_as_advanced(CURL_DISABLE_SHUFFLE_DNS)
option(CURL_DISABLE_SMB "Disable SMB" OFF)
mark_as_advanced(CURL_DISABLE_SMB)
option(CURL_DISABLE_SMTP "Disable SMTP" OFF)
mark_as_advanced(CURL_DISABLE_SMTP)
option(CURL_DISABLE_SOCKETPAIR "Disable use of socketpair for curl_multi_poll" OFF)
mark_as_advanced(CURL_DISABLE_SOCKETPAIR)
option(CURL_DISABLE_WEBSOCKETS "Disable WebSocket" OFF)
mark_as_advanced(CURL_DISABLE_WEBSOCKETS)
option(CURL_DISABLE_TELNET "Disable Telnet" OFF)
mark_as_advanced(CURL_DISABLE_TELNET)
option(CURL_DISABLE_TFTP "Disable TFTP" OFF)
mark_as_advanced(CURL_DISABLE_TFTP)
option(CURL_DISABLE_VERBOSE_STRINGS "Disable verbose strings" OFF)
mark_as_advanced(CURL_DISABLE_VERBOSE_STRINGS)

if(CURL_DISABLE_HTTP)
  set(CURL_DISABLE_ALTSVC ON)
  set(CURL_DISABLE_HSTS ON)
  set(CURL_DISABLE_IPFS ON)
  set(CURL_DISABLE_RTSP ON)
  set(CURL_DISABLE_WEBSOCKETS ON)
endif()

# Corresponds to HTTP_ONLY in lib/curl_setup.h
option(HTTP_ONLY "Disable all protocols except HTTP (This overrides all CURL_DISABLE_* options)" OFF)
mark_as_advanced(HTTP_ONLY)

if(HTTP_ONLY)
  set(CURL_DISABLE_DICT ON)
  set(CURL_DISABLE_FILE ON)
  set(CURL_DISABLE_FTP ON)
  set(CURL_DISABLE_GOPHER ON)
  set(CURL_DISABLE_IMAP ON)
  set(CURL_DISABLE_IPFS ON)
  set(CURL_DISABLE_LDAP ON)
  set(CURL_DISABLE_LDAPS ON)
  set(CURL_DISABLE_MQTT ON)
  set(CURL_DISABLE_POP3 ON)
  set(CURL_DISABLE_RTSP ON)
  set(CURL_DISABLE_SMB ON)
  set(CURL_DISABLE_SMTP ON)
  set(CURL_DISABLE_TELNET ON)
  set(CURL_DISABLE_TFTP ON)
endif()

if(WINDOWS_STORE OR WINCE)
  set(CURL_DISABLE_TELNET ON)  # telnet code needs fixing to compile for UWP.
endif()

set(PERL_FOUND FALSE)
set(PERL_EXECUTABLE "") # No doc/network helper targets.

if(PERL_EXECUTABLE)
  add_custom_target(curl-ca-bundle
    COMMENT "Generating a fresh ca-bundle.crt" VERBATIM USES_TERMINAL
    COMMAND "${PERL_EXECUTABLE}" "${SOURCE_ROOT}/scripts/mk-ca-bundle.pl" -b -l -u "lib/ca-bundle.crt"
    DEPENDS "${SOURCE_ROOT}/scripts/mk-ca-bundle.pl"
  )
  add_custom_target(curl-ca-firefox
    COMMENT "Generating a fresh ca-bundle.crt" VERBATIM USES_TERMINAL
    COMMAND "${PERL_EXECUTABLE}" "${SOURCE_ROOT}/scripts/firefox-db2pem.sh" "lib/ca-bundle.crt"
    DEPENDS "${SOURCE_ROOT}/scripts/firefox-db2pem.sh"
  )
endif()

option(BUILD_LIBCURL_DOCS "Build libcurl man pages" ON)
option(BUILD_MISC_DOCS "Build misc man pages (e.g. curl-config and mk-ca-bundle)" ON)
option(ENABLE_CURL_MANUAL "Build the man page for curl and enable its -M/--manual option" ON)

if((ENABLE_CURL_MANUAL OR BUILD_LIBCURL_DOCS) AND NOT PERL_FOUND)
  message(WARNING "Perl not found. Will not build manuals.")
endif()

# If we are on AIX, do the _ALL_SOURCE magic
if(CMAKE_SYSTEM_NAME STREQUAL "AIX")
  set_property(DIRECTORY APPEND PROPERTY COMPILE_DEFINITIONS "_ALL_SOURCE")
endif()

# If we are on Haiku, make sure that the network library is brought in.
if(CMAKE_SYSTEM_NAME STREQUAL "Haiku")
  list(APPEND CURL_NETWORK_AND_TIME_LIBS "network")
elseif(AMIGA)
  list(APPEND CURL_NETWORK_AND_TIME_LIBS "net" "m" "atomic")
  list(APPEND CMAKE_REQUIRED_LIBRARIES "net" "m" "atomic")
endif()

# Include all the necessary files for macros
include(CMakePushCheckState)
include(CheckFunctionExists)
include(CheckIncludeFile)
include(CheckIncludeFiles)
include(CheckLibraryExists)
include(CheckSymbolExists)
include(CheckTypeSize)
include(CheckCSourceCompiles)

option(_CURL_PREFILL "Fast-track known feature detection results (Windows, some Apple)" "${WIN32}")
if(_CURL_PREFILL)
  if(WIN32)
    include("${SOURCE_ROOT}/CMake/win32-cache.cmake")
  elseif(UNIX)
    include("${SOURCE_ROOT}/CMake/unix-cache.cmake")
    message(STATUS "Pre-filling feature detection results for UNIX")
  endif()
elseif(WIN32)
  message(STATUS "Pre-filling feature detection results disabled.")
elseif(APPLE)
  set(HAVE_EVENTFD 0)
  set(HAVE_GETPASS_R 0)
  set(HAVE_WRITABLE_ARGV 1)
  set(HAVE_SENDMMSG 0)
endif()

if(AMIGA)
  set(HAVE_GETADDRINFO 0)  # Breaks the build when detected and used.
endif()
if(DOS OR AMIGA)
  set(HAVE_TIME_T_UNSIGNED 1)
endif()

if(ENABLE_THREADED_RESOLVER)
  if(WIN32)
    set(USE_THREADS_WIN32 ON)
  else()
    find_package(Threads REQUIRED)
    set(USE_THREADS_POSIX ${CMAKE_USE_PTHREADS_INIT})
    set(HAVE_PTHREAD_H ${CMAKE_USE_PTHREADS_INIT})
    list(APPEND CURL_NETWORK_AND_TIME_LIBS ${CMAKE_THREAD_LIBS_INIT})
  endif()
endif()

# Check for all needed libraries
if(WIN32)
  if(WINCE)
    set(_win32_winsock "ws2")
  else()
    set(_win32_winsock "ws2_32")
  endif()
  set(_win32_crypt32 "crypt32")
  set(_win32_secur32 "secur32")

  if(MINGW32CE)  # FIXME upstream: must specify the full path to avoid CMake converting "ws2" to "ws2.lib"
    set(_win32_winsock "${MINGW32CE_LIBRARY_DIR}/lib${_win32_winsock}.a")
    set(_win32_crypt32 "${MINGW32CE_LIBRARY_DIR}/lib${_win32_crypt32}.a")
    set(_win32_secur32 "${MINGW32CE_LIBRARY_DIR}/lib${_win32_secur32}.a")
  endif()
elseif(DOS)
  if(WATT_ROOT)
    set(USE_WATT32 ON)
    # FIXME upstream: must specify the full path to avoid CMake converting "watt" to "watt.lib"
    list(APPEND CURL_NETWORK_AND_TIME_LIBS "${WATT_ROOT}/lib/libwatt.a")
    include_directories(SYSTEM "${WATT_ROOT}/inc")
    list(APPEND CMAKE_REQUIRED_INCLUDES "${WATT_ROOT}/inc")
  else()
    message(FATAL_ERROR "Set WATT_ROOT variable to the absolute path to the root installation of Watt-32.")
  endif()
elseif(AMIGA)
  if(AMISSL_INCLUDE_DIR AND AMISSL_STUBS_LIBRARY AND AMISSL_AUTO_LIBRARY)
    set(USE_AMISSL ON)
    list(APPEND CMAKE_REQUIRED_INCLUDES "${AMISSL_INCLUDE_DIR}")
    list(APPEND CMAKE_REQUIRED_LIBRARIES "${AMISSL_STUBS_LIBRARY}" "${AMISSL_AUTO_LIBRARY}")
    set(OPENSSL_INCLUDE_DIR "${AMISSL_INCLUDE_DIR}")
    set(OPENSSL_SSL_LIBRARY "${AMISSL_STUBS_LIBRARY}")
    set(OPENSSL_CRYPTO_LIBRARY "${AMISSL_AUTO_LIBRARY}")
    set(CURL_USE_OPENSSL ON)
    set(CURL_CA_FALLBACK ON CACHE BOOL "")
  endif()
elseif(NOT APPLE)
  check_library_exists("socket" "connect" "" HAVE_LIBSOCKET)
  if(HAVE_LIBSOCKET)
    set(CURL_NETWORK_AND_TIME_LIBS "socket" ${CURL_NETWORK_AND_TIME_LIBS})
  endif()
endif()

option(ENABLE_IPV6 "Enable IPv6 support" ON)
mark_as_advanced(ENABLE_IPV6)
if(ENABLE_IPV6)
  include(CheckStructHasMember)
  if(WIN32)
    check_struct_has_member("struct sockaddr_in6" "sin6_scope_id" "winsock2.h;ws2tcpip.h" HAVE_SOCKADDR_IN6_SIN6_SCOPE_ID)
  else()
    check_struct_has_member("struct sockaddr_in6" "sin6_scope_id" "netinet/in.h" HAVE_SOCKADDR_IN6_SIN6_SCOPE_ID)
    check_struct_has_member("struct sockaddr_in6" "sin6_addr" "netinet/in.h" HAVE_SOCKADDR_IN6_SIN6_ADDR)
    if(NOT HAVE_SOCKADDR_IN6_SIN6_ADDR)
      if(NOT DOS AND NOT AMIGA)
        message(WARNING "struct sockaddr_in6 not available, disabling IPv6 support")
      endif()
      set(ENABLE_IPV6 OFF CACHE BOOL "Enable IPv6 support" FORCE)  # Force the feature off as we use this name as guard macro
    endif()

    if(CMAKE_SYSTEM_NAME STREQUAL "Darwin" AND NOT ENABLE_ARES)
      set(_use_core_foundation_and_core_services ON)

      find_library(SYSTEMCONFIGURATION_FRAMEWORK NAMES "SystemConfiguration")
      mark_as_advanced(SYSTEMCONFIGURATION_FRAMEWORK)
      if(NOT SYSTEMCONFIGURATION_FRAMEWORK)
        message(FATAL_ERROR "SystemConfiguration framework not found")
      endif()
      list(APPEND CURL_LIBS "-framework SystemConfiguration")
    endif()
  endif()
endif()
if(ENABLE_IPV6 AND NOT WINCE)
  set(USE_IPV6 ON)
endif()

# Check SSL libraries
option(CURL_ENABLE_SSL "Enable SSL support" ON)

if(CURL_DEFAULT_SSL_BACKEND)
  set(_valid_default_ssl_backend FALSE)
endif()

if(WIN32)
  cmake_dependent_option(CURL_USE_SCHANNEL "Enable Windows native SSL/TLS (Schannel)" OFF CURL_ENABLE_SSL OFF)
  option(CURL_WINDOWS_SSPI "Enable SSPI on Windows" ${CURL_USE_SCHANNEL})
else()
  set(CURL_USE_SCHANNEL OFF)
  set(CURL_WINDOWS_SSPI OFF)
endif()
cmake_dependent_option(CURL_USE_MBEDTLS "Enable mbedTLS for SSL/TLS" OFF CURL_ENABLE_SSL OFF)
cmake_dependent_option(CURL_USE_WOLFSSL "Enable wolfSSL for SSL/TLS" OFF CURL_ENABLE_SSL OFF)
cmake_dependent_option(CURL_USE_GNUTLS "Enable GnuTLS for SSL/TLS" OFF CURL_ENABLE_SSL OFF)
cmake_dependent_option(CURL_USE_RUSTLS "Enable Rustls for SSL/TLS" OFF CURL_ENABLE_SSL OFF)

if(WIN32 OR
   CURL_USE_SCHANNEL OR
   CURL_USE_MBEDTLS OR
   CURL_USE_WOLFSSL OR
   CURL_USE_GNUTLS OR
   CURL_USE_RUSTLS)
  set(_openssl_default OFF)
else()
  set(_openssl_default ON)
endif()
cmake_dependent_option(CURL_USE_OPENSSL "Enable OpenSSL for SSL/TLS" ${_openssl_default} CURL_ENABLE_SSL OFF)
option(USE_OPENSSL_QUIC "Use OpenSSL and nghttp3 libraries for HTTP/3 support" OFF)
if(USE_OPENSSL_QUIC AND NOT CURL_USE_OPENSSL)
  message(WARNING "OpenSSL QUIC has been requested, but without enabling OpenSSL. Will not enable QUIC.")
  set(USE_OPENSSL_QUIC OFF)
endif()
option(CURL_DISABLE_OPENSSL_AUTO_LOAD_CONFIG "Disable automatic loading of OpenSSL configuration" OFF)

curl_count_true(_enabled_ssl_options_count
  CURL_USE_SCHANNEL
  CURL_USE_OPENSSL
  CURL_USE_MBEDTLS
  CURL_USE_WOLFSSL
  CURL_USE_GNUTLS
  CURL_USE_RUSTLS
)
if(_enabled_ssl_options_count GREATER 1)
  set(CURL_WITH_MULTI_SSL ON)
elseif(_enabled_ssl_options_count EQUAL 0)
  set(CURL_DISABLE_HSTS ON)
endif()

if(CURL_USE_SCHANNEL)
  if(WINDOWS_STORE)
    message(FATAL_ERROR "UWP does not support Schannel.")
  endif()
  set(_ssl_enabled ON)
  set(USE_SCHANNEL ON)  # Windows native SSL/TLS support
  set(USE_WINDOWS_SSPI ON)  # CURL_USE_SCHANNEL requires CURL_WINDOWS_SSPI

  if(CURL_DEFAULT_SSL_BACKEND AND CURL_DEFAULT_SSL_BACKEND STREQUAL "schannel")
    set(_valid_default_ssl_backend TRUE)
  endif()
endif()
if(CURL_WINDOWS_SSPI AND NOT WINDOWS_STORE)
  set(USE_WINDOWS_SSPI ON)
endif()

if(APPLE)
  option(USE_APPLE_SECTRUST "Use Apple OS-native certificate verification" OFF)
  if(USE_APPLE_SECTRUST)
    if(NOT CURL_USE_OPENSSL AND NOT CURL_USE_GNUTLS)
      message(FATAL_ERROR "Apple SecTrust is only supported with Openssl/GnuTLS")
    endif()
    find_library(COREFOUNDATION_FRAMEWORK NAMES "Security")
    mark_as_advanced(COREFOUNDATION_FRAMEWORK)
    if(NOT COREFOUNDATION_FRAMEWORK)
      message(FATAL_ERROR "Security framework not found")
    endif()
    list(APPEND CURL_LIBS "-framework Security")

    set(_use_core_foundation_and_core_services ON)
    message(STATUS "Apple OS-native certificate verification enabled")
  endif()
else()
  set(USE_APPLE_SECTRUST OFF)
endif()

if(_use_core_foundation_and_core_services)
  find_library(COREFOUNDATION_FRAMEWORK NAMES "CoreFoundation")
  mark_as_advanced(COREFOUNDATION_FRAMEWORK)
  if(NOT COREFOUNDATION_FRAMEWORK)
    message(FATAL_ERROR "CoreFoundation framework not found")
  endif()
  list(APPEND CURL_LIBS "-framework CoreFoundation")

  find_library(CORESERVICES_FRAMEWORK NAMES "CoreServices")
  mark_as_advanced(CORESERVICES_FRAMEWORK)
  if(NOT CORESERVICES_FRAMEWORK)
    message(FATAL_ERROR "CoreServices framework not found")
  endif()
  list(APPEND CURL_LIBS "-framework CoreServices")
endif()

if(CURL_USE_OPENSSL)
  find_package(OpenSSL REQUIRED)
  set(_ssl_enabled ON)
  set(USE_OPENSSL ON)

  # Depend on OpenSSL via imported targets. This allows our dependents to
  # get our dependencies transitively.
  list(APPEND CURL_LIBS OpenSSL::SSL OpenSSL::Crypto)
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE "openssl")

  if(CURL_DEFAULT_SSL_BACKEND AND CURL_DEFAULT_SSL_BACKEND STREQUAL "openssl")
    set(_valid_default_ssl_backend TRUE)
  endif()
  set(_curl_ca_bundle_supported TRUE)

  cmake_push_check_state()
  list(APPEND CMAKE_REQUIRED_LIBRARIES OpenSSL::SSL OpenSSL::Crypto)
  if(NOT DEFINED HAVE_BORINGSSL)
    check_symbol_exists("OPENSSL_IS_BORINGSSL" "openssl/base.h" HAVE_BORINGSSL)
  endif()
  if(NOT DEFINED HAVE_AWSLC)
    check_symbol_exists("OPENSSL_IS_AWSLC" "openssl/base.h" HAVE_AWSLC)
  endif()
  if(NOT DEFINED HAVE_LIBRESSL)
    check_symbol_exists("LIBRESSL_VERSION_NUMBER" "openssl/opensslv.h" HAVE_LIBRESSL)
  endif()
  cmake_pop_check_state()

  if(HAVE_BORINGSSL OR HAVE_AWSLC)
    if(OPENSSL_USE_STATIC_LIBS AND CMAKE_C_COMPILER_ID MATCHES "Clang")
      list(APPEND CURL_LIBS "stdc++")
      list(APPEND CMAKE_REQUIRED_LIBRARIES "stdc++")
    endif()
  endif()

  if(HAVE_BORINGSSL)
    set(_openssl "BoringSSL")
  elseif(HAVE_AWSLC)
    set(_openssl "AWS-LC")
  elseif(HAVE_LIBRESSL)
    set(_openssl "LibreSSL")
  elseif(USE_AMISSL)
    set(_openssl "AmiSSL")
  else()
    set(_openssl "OpenSSL")
  endif()
endif()

if(CURL_USE_MBEDTLS)
  find_package(MbedTLS REQUIRED)
  if(MBEDTLS_VERSION VERSION_LESS 3.2.0)
    message(FATAL_ERROR "mbedTLS v3.2.0 or newer is required.")
  endif()
  set(_ssl_enabled ON)
  set(USE_MBEDTLS ON)
  list(APPEND CURL_LIBS ${MBEDTLS_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${MBEDTLS_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${MBEDTLS_PC_REQUIRES})
  include_directories(SYSTEM ${MBEDTLS_INCLUDE_DIRS})
  link_directories(${MBEDTLS_LIBRARY_DIRS})
  if(MBEDTLS_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${MBEDTLS_CFLAGS}")
  endif()

  if(CURL_DEFAULT_SSL_BACKEND AND CURL_DEFAULT_SSL_BACKEND STREQUAL "mbedtls")
    set(_valid_default_ssl_backend TRUE)
  endif()
  set(_curl_ca_bundle_supported TRUE)

  if(MBEDTLS_VERSION VERSION_GREATER_EQUAL 4.0.0)
    set(HAVE_MBEDTLS_DES_CRYPT_ECB 0)  # pre-fill detection result
  endif()
  if(NOT DEFINED HAVE_MBEDTLS_DES_CRYPT_ECB)
    cmake_push_check_state()
    list(APPEND CMAKE_REQUIRED_INCLUDES "${MBEDTLS_INCLUDE_DIRS}")
    list(APPEND CMAKE_REQUIRED_LIBRARIES "${MBEDTLS_LIBRARIES}")
    curl_required_libpaths("${MBEDTLS_LIBRARY_DIRS}")
    check_function_exists("mbedtls_des_crypt_ecb" HAVE_MBEDTLS_DES_CRYPT_ECB)  # in mbedTLS <4
    cmake_pop_check_state()
  endif()
endif()

if(CURL_USE_WOLFSSL)
  find_package(WolfSSL REQUIRED)
  set(_ssl_enabled ON)
  set(USE_WOLFSSL ON)
  list(APPEND CURL_LIBS ${WOLFSSL_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${WOLFSSL_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${WOLFSSL_PC_REQUIRES})
  include_directories(SYSTEM ${WOLFSSL_INCLUDE_DIRS})
  link_directories(${WOLFSSL_LIBRARY_DIRS})
  if(WOLFSSL_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${WOLFSSL_CFLAGS}")
  endif()

  if(CURL_DEFAULT_SSL_BACKEND AND CURL_DEFAULT_SSL_BACKEND STREQUAL "wolfssl")
    set(_valid_default_ssl_backend TRUE)
  endif()
  set(_curl_ca_bundle_supported TRUE)
endif()

if(CURL_USE_GNUTLS)
  find_package(GnuTLS REQUIRED)
  list(APPEND CURL_LIBS ${GNUTLS_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${GNUTLS_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${GNUTLS_PC_REQUIRES})
  include_directories(SYSTEM ${GNUTLS_INCLUDE_DIRS})
  link_directories(${GNUTLS_LIBRARY_DIRS})
  if(GNUTLS_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${GNUTLS_CFLAGS}")
  endif()

  find_package(Nettle REQUIRED)
  set(_ssl_enabled ON)
  set(USE_GNUTLS ON)
  list(APPEND CURL_LIBS ${NETTLE_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${NETTLE_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${NETTLE_PC_REQUIRES})
  include_directories(SYSTEM ${NETTLE_INCLUDE_DIRS})
  link_directories(${NETTLE_LIBRARY_DIRS})
  if(NETTLE_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${NETTLE_CFLAGS}")
  endif()

  if(CURL_DEFAULT_SSL_BACKEND AND CURL_DEFAULT_SSL_BACKEND STREQUAL "gnutls")
    set(_valid_default_ssl_backend TRUE)
  endif()
  set(_curl_ca_bundle_supported TRUE)

  if(NOT DEFINED HAVE_GNUTLS_SRP AND NOT CURL_DISABLE_SRP)
    cmake_push_check_state()
    list(APPEND CMAKE_REQUIRED_INCLUDES "${GNUTLS_INCLUDE_DIRS}")
    list(APPEND CMAKE_REQUIRED_LIBRARIES "${GNUTLS_LIBRARIES}")
    curl_required_libpaths("${GNUTLS_LIBRARY_DIRS}")
    check_symbol_exists("gnutls_srp_verifier" "gnutls/gnutls.h" HAVE_GNUTLS_SRP)
    cmake_pop_check_state()
  endif()
endif()

if(CURL_USE_RUSTLS)
  find_package(Rustls REQUIRED)
  set(_ssl_enabled ON)
  set(USE_RUSTLS ON)
  list(APPEND CURL_LIBS ${RUSTLS_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${RUSTLS_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${RUSTLS_PC_REQUIRES})
  include_directories(SYSTEM ${RUSTLS_INCLUDE_DIRS})
  link_directories(${RUSTLS_LIBRARY_DIRS})
  if(RUSTLS_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${RUSTLS_CFLAGS}")
  endif()

  if(NOT DEFINED HAVE_RUSTLS_SUPPORTED_HPKE)
    if(RUSTLS_VERSION AND RUSTLS_VERSION VERSION_GREATER_EQUAL 0.15)
      set(HAVE_RUSTLS_SUPPORTED_HPKE TRUE)
    elseif(NOT RUSTLS_VERSION)
      cmake_push_check_state()
      list(APPEND CMAKE_REQUIRED_INCLUDES "${RUSTLS_INCLUDE_DIRS}")
      list(APPEND CMAKE_REQUIRED_LIBRARIES "${RUSTLS_LIBRARIES}")
      curl_required_libpaths("${RUSTLS_LIBRARY_DIRS}")
      check_symbol_exists("rustls_supported_hpke" "rustls.h" HAVE_RUSTLS_SUPPORTED_HPKE)
      cmake_pop_check_state()
    endif()
  endif()
  if(NOT HAVE_RUSTLS_SUPPORTED_HPKE)
    message(FATAL_ERROR "rustls-ffi library does not provide rustls_supported_hpke function. Required version is 0.15 or newer.")
  endif()

  if(CURL_DEFAULT_SSL_BACKEND AND CURL_DEFAULT_SSL_BACKEND STREQUAL "rustls")
    set(_valid_default_ssl_backend TRUE)
  endif()
  set(_curl_ca_bundle_supported TRUE)
endif()

if(CURL_DEFAULT_SSL_BACKEND AND NOT _valid_default_ssl_backend)
  message(FATAL_ERROR "CURL_DEFAULT_SSL_BACKEND '${CURL_DEFAULT_SSL_BACKEND}' not enabled.")
endif()

# Keep ZLIB detection after TLS detection,
# and before calling curl_openssl_check_exists().

set(HAVE_LIBZ OFF)
curl_dependency_option(CURL_ZLIB ZLIB "ZLIB")
if(ZLIB_FOUND)
  set(HAVE_LIBZ ON)
  # Depend on ZLIB via imported targets. This allows our dependents to
  # get our dependencies transitively.
  list(APPEND CURL_LIBS ZLIB::ZLIB)
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE "zlib")
endif()

set(HAVE_BROTLI OFF)
curl_dependency_option(CURL_BROTLI Brotli "brotli")
if(BROTLI_FOUND)
  set(HAVE_BROTLI ON)
  list(APPEND CURL_LIBS ${BROTLI_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${BROTLI_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${BROTLI_PC_REQUIRES})
  include_directories(SYSTEM ${BROTLI_INCLUDE_DIRS})
  link_directories(${BROTLI_LIBRARY_DIRS})
  if(BROTLI_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${BROTLI_CFLAGS}")
  endif()
endif()

set(HAVE_ZSTD OFF)
curl_dependency_option(CURL_ZSTD Zstd "zstd")
if(ZSTD_FOUND)
  if(ZSTD_VERSION VERSION_GREATER_EQUAL 1.0.0)
    set(HAVE_ZSTD ON)
    list(APPEND CURL_LIBS ${ZSTD_LIBRARIES})
    list(APPEND CURL_LIBDIRS ${ZSTD_LIBRARY_DIRS})
    list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${ZSTD_PC_REQUIRES})
    include_directories(SYSTEM ${ZSTD_INCLUDE_DIRS})
    link_directories(${ZSTD_LIBRARY_DIRS})
    if(ZSTD_CFLAGS)
      string(APPEND CMAKE_C_FLAGS " ${ZSTD_CFLAGS}")
    endif()
  else()
    message(WARNING "zstd v1.0.0 or newer is required, disabling zstd support.")
  endif()
endif()

# Check function in an OpenSSL-like TLS backend.
macro(curl_openssl_check_exists)
  cmake_push_check_state()
  if(USE_OPENSSL)
    list(APPEND CMAKE_REQUIRED_LIBRARIES OpenSSL::SSL OpenSSL::Crypto)
    list(APPEND CMAKE_REQUIRED_DEFINITIONS "-DOPENSSL_SUPPRESS_DEPRECATED")  # for SSL_CTX_set_srp_username deprecated since 3.0.0
    if(HAVE_LIBZ)
      list(APPEND CMAKE_REQUIRED_LIBRARIES ZLIB::ZLIB)
    endif()
    if(WIN32 AND NOT WINCE)
      list(APPEND CMAKE_REQUIRED_LIBRARIES "bcrypt")  # for OpenSSL/LibreSSL
    endif()
  endif()
  if(USE_WOLFSSL)
    list(APPEND CMAKE_REQUIRED_INCLUDES "${WOLFSSL_INCLUDE_DIRS}")
    list(APPEND CMAKE_REQUIRED_LIBRARIES "${WOLFSSL_LIBRARIES}")
    curl_required_libpaths("${WOLFSSL_LIBRARY_DIRS}")
    if(HAVE_LIBZ)
      list(APPEND CMAKE_REQUIRED_LIBRARIES ZLIB::ZLIB)  # Public wolfSSL headers also require zlib headers
    endif()
    list(APPEND CMAKE_REQUIRED_DEFINITIONS "-DHAVE_UINTPTR_T")  # to pull in stdint.h (as of wolfSSL v5.5.4)
  endif()
  if(WIN32)
    list(APPEND CMAKE_REQUIRED_LIBRARIES "${_win32_winsock}" "${_win32_crypt32}")  # for OpenSSL/wolfSSL
  endif()
  if(${ARGC} EQUAL 2)
    check_function_exists(${ARGN})
  else()
    check_symbol_exists(${ARGN})  # Uses CMAKE_REQUIRED_INCLUDES and CMAKE_REQUIRED_DEFINITIONS
  endif()
  cmake_pop_check_state()
endmacro()

# Ensure that OpenSSL (or fork) or wolfSSL actually supports QUICTLS API.
macro(curl_openssl_check_quic)
  if(USE_OPENSSL AND NOT USE_OPENSSL_QUIC)
    if(OPENSSL_VERSION VERSION_GREATER_EQUAL 3.5.0)
      if(NOT DEFINED HAVE_SSL_SET_QUIC_TLS_CBS)
        curl_openssl_check_exists("SSL_set_quic_tls_cbs" HAVE_SSL_SET_QUIC_TLS_CBS)
      endif()
    else()
      if(NOT DEFINED HAVE_SSL_SET_QUIC_USE_LEGACY_CODEPOINT)
        curl_openssl_check_exists("SSL_set_quic_use_legacy_codepoint" HAVE_SSL_SET_QUIC_USE_LEGACY_CODEPOINT)
      endif()
    endif()
  endif()
  if(USE_WOLFSSL AND NOT DEFINED HAVE_WOLFSSL_SET_QUIC_USE_LEGACY_CODEPOINT)
    curl_openssl_check_exists("wolfSSL_set_quic_use_legacy_codepoint" HAVE_WOLFSSL_SET_QUIC_USE_LEGACY_CODEPOINT)
  endif()
  if(NOT HAVE_SSL_SET_QUIC_TLS_CBS AND
     NOT HAVE_SSL_SET_QUIC_USE_LEGACY_CODEPOINT AND
     NOT HAVE_WOLFSSL_SET_QUIC_USE_LEGACY_CODEPOINT)
    message(FATAL_ERROR "QUICTLS API support is missing from OpenSSL/fork/wolfSSL. Try setting -DOPENSSL_ROOT_DIR")
  endif()
endmacro()

if(USE_WOLFSSL)
  curl_openssl_check_exists("wolfSSL_get_peer_certificate" HAVE_WOLFSSL_GET_PEER_CERTIFICATE)
  curl_openssl_check_exists("wolfSSL_UseALPN" HAVE_WOLFSSL_USEALPN)
  curl_openssl_check_exists("wolfSSL_DES_ecb_encrypt" HAVE_WOLFSSL_DES_ECB_ENCRYPT)
  curl_openssl_check_exists("wolfSSL_BIO_new" HAVE_WOLFSSL_BIO_NEW)
  curl_openssl_check_exists("wolfSSL_BIO_set_shutdown" HAVE_WOLFSSL_BIO_SET_SHUTDOWN)
endif()

if(USE_OPENSSL)
  if(NOT DEFINED HAVE_DES_ECB_ENCRYPT)
    curl_openssl_check_exists("DES_ecb_encrypt" "openssl/des.h" HAVE_DES_ECB_ENCRYPT)
  endif()
  if(NOT DEFINED HAVE_SSL_SET0_WBIO)
    curl_openssl_check_exists("SSL_set0_wbio" HAVE_SSL_SET0_WBIO)
  endif()
  if(NOT DEFINED HAVE_OPENSSL_SRP AND NOT CURL_DISABLE_SRP)
    curl_openssl_check_exists("SSL_CTX_set_srp_username" "openssl/ssl.h" HAVE_OPENSSL_SRP)
  endif()
endif()

""",
    'curl-configuration-2': r"""option(USE_HTTPSRR "Enable HTTPS RR support" OFF)
option(USE_ECH "Enable ECH support" OFF)
if(USE_ECH)
  if(USE_OPENSSL OR USE_WOLFSSL OR USE_RUSTLS)
    # Be sure that the TLS library actually supports ECH.
    if(USE_WOLFSSL)
      curl_openssl_check_exists("wolfSSL_CTX_GenerateEchConfig" HAVE_WOLFSSL_CTX_GENERATEECHCONFIG)
    endif()
    if(USE_OPENSSL)
      curl_openssl_check_exists("SSL_set1_ech_config_list" HAVE_SSL_SET1_ECH_CONFIG_LIST)
    endif()
    if(HAVE_WOLFSSL_CTX_GENERATEECHCONFIG OR
       HAVE_SSL_SET1_ECH_CONFIG_LIST OR
       USE_RUSTLS)
      set(HAVE_ECH 1)
    endif()
    if(NOT HAVE_ECH)
      message(FATAL_ERROR "ECH support missing in OpenSSL/BoringSSL/AWS-LC/wolfSSL/rustls-ffi")
    else()
      message(STATUS "ECH enabled")
      # ECH wants HTTPSRR
      set(USE_HTTPSRR ON)
      message(STATUS "HTTPSRR enabled")
    endif()
  else()
    message(FATAL_ERROR "ECH requires ECH-enabled OpenSSL, BoringSSL, AWS-LC, wolfSSL or rustls-ffi")
  endif()
endif()

option(USE_SSLS_EXPORT "Enable SSL session export support" OFF)
if(USE_SSLS_EXPORT)
  if(_ssl_enabled)
    message(STATUS "SSL export enabled.")
  else()
    message(WARNING "SSL session export requires SSL enabled")
  endif()
endif()

option(USE_NGHTTP2 "Use nghttp2 library" ON)
if(USE_NGHTTP2)
  find_package(NGHTTP2)
  if(NGHTTP2_FOUND)
    list(APPEND CURL_LIBS ${NGHTTP2_LIBRARIES})
    list(APPEND CURL_LIBDIRS ${NGHTTP2_LIBRARY_DIRS})
    list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${NGHTTP2_PC_REQUIRES})
    include_directories(SYSTEM ${NGHTTP2_INCLUDE_DIRS})
    link_directories(${NGHTTP2_LIBRARY_DIRS})
    if(NGHTTP2_CFLAGS)
      string(APPEND CMAKE_C_FLAGS " ${NGHTTP2_CFLAGS}")
    endif()
  else()
    set(USE_NGHTTP2 OFF)
  endif()
endif()

option(USE_NGTCP2 "Use ngtcp2 and nghttp3 libraries for HTTP/3 support" OFF)
if(USE_NGTCP2)
  if(CURL_WITH_MULTI_SSL)
    message(FATAL_ERROR "MultiSSL cannot be enabled with HTTP/3 and vice versa.")
  elseif(USE_OPENSSL OR USE_WOLFSSL)
    if(USE_WOLFSSL)
      find_package(NGTCP2 REQUIRED COMPONENTS "wolfSSL")
    elseif(HAVE_BORINGSSL OR HAVE_AWSLC)
      find_package(NGTCP2 REQUIRED COMPONENTS "BoringSSL")
    elseif(OPENSSL_VERSION VERSION_GREATER_EQUAL 3.5.0 AND NOT USE_OPENSSL_QUIC)
      find_package(NGTCP2 REQUIRED COMPONENTS "ossl")
      if(NGTCP2_VERSION VERSION_LESS 1.12.0)
        message(FATAL_ERROR "ngtcp2 1.12.0 or upper required for OpenSSL")
      endif()
      set(OPENSSL_QUIC_API2 1)
    elseif(HAVE_LIBRESSL)
      find_package(NGTCP2 COMPONENTS "LibreSSL")
      if(NOT NGTCP2_FOUND)
        find_package(NGTCP2 REQUIRED COMPONENTS "quictls")  # for ngtcp2 <1.15.0
      endif()
    else()
      find_package(NGTCP2 REQUIRED COMPONENTS "quictls")
      set(_openssl "quictls")
    endif()
    curl_openssl_check_quic()
  elseif(USE_GNUTLS)
    find_package(NGTCP2 REQUIRED "GnuTLS")
  else()
    message(FATAL_ERROR "ngtcp2 requires a supported TLS-backend")
  endif()
  list(APPEND CURL_LIBS ${NGTCP2_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${NGTCP2_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${NGTCP2_PC_REQUIRES})
  include_directories(SYSTEM ${NGTCP2_INCLUDE_DIRS})
  link_directories(${NGTCP2_LIBRARY_DIRS})
  if(NGTCP2_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${NGTCP2_CFLAGS}")
  endif()

  find_package(NGHTTP3 REQUIRED)
  set(USE_NGHTTP3 ON)
  list(APPEND CURL_LIBS ${NGHTTP3_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${NGHTTP3_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${NGHTTP3_PC_REQUIRES})
  include_directories(SYSTEM ${NGHTTP3_INCLUDE_DIRS})
  link_directories(${NGHTTP3_LIBRARY_DIRS})
  if(NGHTTP3_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${NGHTTP3_CFLAGS}")
  endif()
endif()

option(USE_QUICHE "Use quiche library for HTTP/3 support" OFF)
if(USE_QUICHE)
  if(USE_NGTCP2)
    message(FATAL_ERROR "Only one HTTP/3 backend can be selected")
  elseif(CURL_WITH_MULTI_SSL)
    message(FATAL_ERROR "MultiSSL cannot be enabled with HTTP/3 and vice versa.")
  endif()
  find_package(Quiche REQUIRED)
  if(NOT HAVE_BORINGSSL)
    message(FATAL_ERROR "quiche requires BoringSSL")
  endif()
  curl_openssl_check_quic()
  list(APPEND CURL_LIBS ${QUICHE_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${QUICHE_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${QUICHE_PC_REQUIRES})
  include_directories(SYSTEM ${QUICHE_INCLUDE_DIRS})
  link_directories(${QUICHE_LIBRARY_DIRS})
  if(QUICHE_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${QUICHE_CFLAGS}")
  endif()
  if(NOT DEFINED HAVE_QUICHE_CONN_SET_QLOG_FD)
    cmake_push_check_state()
    list(APPEND CMAKE_REQUIRED_INCLUDES "${QUICHE_INCLUDE_DIRS}")
    list(APPEND CMAKE_REQUIRED_LIBRARIES "${QUICHE_LIBRARIES}")
    check_symbol_exists("quiche_conn_set_qlog_fd" "quiche.h" HAVE_QUICHE_CONN_SET_QLOG_FD)
    cmake_pop_check_state()
  endif()
endif()

if(USE_OPENSSL_QUIC)
  if(USE_NGTCP2 OR USE_QUICHE)
    message(FATAL_ERROR "Only one HTTP/3 backend can be selected")
  elseif(CURL_WITH_MULTI_SSL)
    message(FATAL_ERROR "MultiSSL cannot be enabled with HTTP/3 and vice versa.")
  endif()
  find_package(OpenSSL 3.3.0 REQUIRED)

  find_package(NGHTTP3 REQUIRED)
  set(USE_NGHTTP3 ON)
  list(APPEND CURL_LIBS ${NGHTTP3_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${NGHTTP3_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${NGHTTP3_PC_REQUIRES})
  include_directories(SYSTEM ${NGHTTP3_INCLUDE_DIRS})
  link_directories(${NGHTTP3_LIBRARY_DIRS})
  if(NGHTTP3_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${NGHTTP3_CFLAGS}")
  endif()
endif()

if(NOT CURL_DISABLE_SRP AND (HAVE_GNUTLS_SRP OR HAVE_OPENSSL_SRP))
  set(USE_TLS_SRP 1)
endif()

if(NOT CURL_DISABLE_LDAP)
  if(WIN32 AND NOT WINDOWS_STORE AND NOT WINCE)
    option(USE_WIN32_LDAP "Use Windows LDAP implementation" ON)
    if(USE_WIN32_LDAP)
      list(APPEND CURL_LIBS "wldap32")
      if(NOT CURL_DISABLE_LDAPS)
        set(HAVE_LDAP_SSL ON)
      endif()
    endif()
  endif()

  # Now that we know, we are not using Windows LDAP...
  if(NOT USE_WIN32_LDAP)
    # Check for LDAP
    cmake_push_check_state()
    if(USE_OPENSSL)
      list(APPEND CMAKE_REQUIRED_LIBRARIES OpenSSL::SSL OpenSSL::Crypto)
    endif()
    find_package(LDAP)
    if(LDAP_FOUND)
      set(HAVE_LBER_H 1)
      set(CURL_LIBS ${LDAP_LIBRARIES} ${CURL_LIBS})
      list(APPEND CURL_LIBDIRS ${LDAP_LIBRARY_DIRS})
      if(LDAP_PC_REQUIRES)
        set(LIBCURL_PC_REQUIRES_PRIVATE ${LDAP_PC_REQUIRES} ${LIBCURL_PC_REQUIRES_PRIVATE})
      endif()
      include_directories(SYSTEM ${LDAP_INCLUDE_DIRS})
      link_directories(${LDAP_LIBRARY_DIRS})
      if(LDAP_CFLAGS)
        string(APPEND CMAKE_C_FLAGS " ${LDAP_CFLAGS}")
      endif()

      # LDAP feature checks

      list(APPEND CMAKE_REQUIRED_DEFINITIONS "-DLDAP_DEPRECATED=1")
      list(APPEND CMAKE_REQUIRED_LIBRARIES "${LDAP_LIBRARIES}")
      curl_required_libpaths("${LDAP_LIBRARY_DIRS}")

      check_function_exists("ldap_url_parse" HAVE_LDAP_URL_PARSE)
      check_function_exists("ldap_init_fd" HAVE_LDAP_INIT_FD)

      check_include_file("ldap_ssl.h" HAVE_LDAP_SSL_H)

      if(HAVE_LDAP_INIT_FD)
        set(USE_OPENLDAP ON)
      endif()
      if(NOT CURL_DISABLE_LDAPS)
        set(HAVE_LDAP_SSL ON)
      endif()
    else()
      message(STATUS "LDAP not found. CURL_DISABLE_LDAP set ON")
      set(CURL_DISABLE_LDAP ON CACHE BOOL "" FORCE)
    endif()
    cmake_pop_check_state()
  endif()
endif()

# No ldap, no ldaps.
if(CURL_DISABLE_LDAP)
  if(NOT CURL_DISABLE_LDAPS)
    message(STATUS "LDAP needs to be enabled to support LDAPS")
    set(CURL_DISABLE_LDAPS ON CACHE BOOL "" FORCE)
  endif()
endif()

if(WIN32)
  option(USE_WIN32_IDN "Use WinIDN for IDN support" OFF)
  if(USE_WIN32_IDN)
    list(APPEND CURL_LIBS "normaliz")
  endif()
else()
  set(USE_WIN32_IDN OFF)
endif()

if(APPLE)
  option(USE_APPLE_IDN "Use Apple built-in IDN support" OFF)
  if(USE_APPLE_IDN)
    cmake_push_check_state()
    list(APPEND CMAKE_REQUIRED_LIBRARIES "icucore")
    check_symbol_exists("uidna_openUTS46" "unicode/uidna.h" HAVE_APPLE_IDN)
    cmake_pop_check_state()
    if(HAVE_APPLE_IDN)
      list(APPEND CURL_LIBS "icucore" "iconv")
    else()
      set(USE_APPLE_IDN OFF)
    endif()
  endif()
else()
  set(USE_APPLE_IDN OFF)
endif()

# Check for libidn2
option(USE_LIBIDN2 "Use libidn2 for IDN support" ON)
set(HAVE_IDN2_H OFF)
set(HAVE_LIBIDN2 OFF)
if(USE_LIBIDN2 AND NOT USE_APPLE_IDN AND NOT USE_WIN32_IDN)
  find_package(Libidn2)
  if(LIBIDN2_FOUND)
    set(CURL_LIBS ${LIBIDN2_LIBRARIES} ${CURL_LIBS})
    list(APPEND CURL_LIBDIRS ${LIBIDN2_LIBRARY_DIRS})
    set(LIBCURL_PC_REQUIRES_PRIVATE ${LIBIDN2_PC_REQUIRES} ${LIBCURL_PC_REQUIRES_PRIVATE})
    include_directories(SYSTEM ${LIBIDN2_INCLUDE_DIRS})
    link_directories(${LIBIDN2_LIBRARY_DIRS})
    if(LIBIDN2_CFLAGS)
      string(APPEND CMAKE_C_FLAGS " ${LIBIDN2_CFLAGS}")
    endif()
    set(HAVE_IDN2_H 1)
    set(HAVE_LIBIDN2 1)
  endif()
endif()

# libpsl
option(CURL_USE_LIBPSL "Use libpsl" ON)
mark_as_advanced(CURL_USE_LIBPSL)
set(USE_LIBPSL OFF)

if(CURL_USE_LIBPSL)
  find_package(Libpsl REQUIRED)
  list(APPEND CURL_LIBS ${LIBPSL_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${LIBPSL_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${LIBPSL_PC_REQUIRES})
  include_directories(SYSTEM ${LIBPSL_INCLUDE_DIRS})
  link_directories(${LIBPSL_LIBRARY_DIRS})
  if(LIBPSL_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${LIBPSL_CFLAGS}")
  endif()
  set(USE_LIBPSL ON)
endif()

# libssh2
option(CURL_USE_LIBSSH2 "Use libssh2" ON)
mark_as_advanced(CURL_USE_LIBSSH2)
set(USE_LIBSSH2 OFF)

if(CURL_USE_LIBSSH2)
  find_package(Libssh2)
  if(LIBSSH2_FOUND)
    set(CURL_LIBS ${LIBSSH2_LIBRARIES} ${CURL_LIBS})  # keep it before TLS-crypto, compression
    list(APPEND CURL_LIBDIRS ${LIBSSH2_LIBRARY_DIRS})
    set(LIBCURL_PC_REQUIRES_PRIVATE ${LIBSSH2_PC_REQUIRES} ${LIBCURL_PC_REQUIRES_PRIVATE})
    include_directories(SYSTEM ${LIBSSH2_INCLUDE_DIRS})
    link_directories(${LIBSSH2_LIBRARY_DIRS})
    if(LIBSSH2_CFLAGS)
      string(APPEND CMAKE_C_FLAGS " ${LIBSSH2_CFLAGS}")
    endif()
    set(USE_LIBSSH2 ON)
  endif()
endif()

# libssh
option(CURL_USE_LIBSSH "Use libssh" OFF)
mark_as_advanced(CURL_USE_LIBSSH)
if(NOT USE_LIBSSH2 AND CURL_USE_LIBSSH)
  find_package(Libssh REQUIRED)
  set(CURL_LIBS ${LIBSSH_LIBRARIES} ${CURL_LIBS})  # keep it before TLS-crypto, compression
  list(APPEND CURL_LIBDIRS ${LIBSSH_LIBRARY_DIRS})
  set(LIBCURL_PC_REQUIRES_PRIVATE ${LIBSSH_PC_REQUIRES} ${LIBCURL_PC_REQUIRES_PRIVATE})
  include_directories(SYSTEM ${LIBSSH_INCLUDE_DIRS})
  link_directories(${LIBSSH_LIBRARY_DIRS})
  if(LIBSSH_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${LIBSSH_CFLAGS}")
  endif()
  set(USE_LIBSSH ON)
endif()

option(CURL_USE_GSASL "Use libgsasl" OFF)
mark_as_advanced(CURL_USE_GSASL)
if(CURL_USE_GSASL)
  find_package(Libgsasl REQUIRED)
  list(APPEND CURL_LIBS ${LIBGSASL_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${LIBGSASL_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${LIBGSASL_PC_REQUIRES})
  include_directories(SYSTEM ${LIBGSASL_INCLUDE_DIRS})
  link_directories(${LIBGSASL_LIBRARY_DIRS})
  if(LIBGSASL_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${LIBGSASL_CFLAGS}")
  endif()
  set(USE_GSASL ON)
endif()

option(CURL_USE_GSSAPI "Use GSSAPI implementation" OFF)
mark_as_advanced(CURL_USE_GSSAPI)

if(CURL_USE_GSSAPI)
  find_package(GSS)

  set(HAVE_GSSAPI ${GSS_FOUND})
  if(GSS_FOUND)
    list(APPEND CURL_LIBS ${GSS_LIBRARIES})
    list(APPEND CURL_LIBDIRS ${GSS_LIBRARY_DIRS})
    list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${GSS_PC_REQUIRES})
    include_directories(SYSTEM ${GSS_INCLUDE_DIRS})
    link_directories(${GSS_LIBRARY_DIRS})
    if(GSS_CFLAGS)
      string(APPEND CMAKE_C_FLAGS " ${GSS_CFLAGS}")
    endif()

    if(GSS_FLAVOUR STREQUAL "GNU")
      set(HAVE_GSSGNU 1)
    elseif(GSS_VERSION)  # MIT
      set(CURL_KRB5_VERSION "\"${GSS_VERSION}\"")
    endif()
  else()
    message(WARNING "GSSAPI has been requested, but no supporting libraries found. Skipping.")
  endif()
endif()

# libuv
option(CURL_USE_LIBUV "Use libuv for event-based tests" OFF)
if(CURL_USE_LIBUV)
  if(NOT ENABLE_DEBUG)
    message(FATAL_ERROR "Using libuv without debug support enabled is useless")
  endif()
  find_package(Libuv REQUIRED)
  list(APPEND CURL_LIBS ${LIBUV_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${LIBUV_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${LIBUV_PC_REQUIRES})
  include_directories(SYSTEM ${LIBUV_INCLUDE_DIRS})
  link_directories(${LIBUV_LIBRARY_DIRS})
  if(LIBUV_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${LIBUV_CFLAGS}")
  endif()
  set(USE_LIBUV ON)
  set(HAVE_UV_H ON)
endif()

option(USE_LIBRTMP "Enable librtmp from rtmpdump" OFF)
if(USE_LIBRTMP)
  find_package(Librtmp REQUIRED)
  list(APPEND CURL_LIBS ${LIBRTMP_LIBRARIES})
  list(APPEND CURL_LIBDIRS ${LIBRTMP_LIBRARY_DIRS})
  list(APPEND LIBCURL_PC_REQUIRES_PRIVATE ${LIBRTMP_PC_REQUIRES})
  include_directories(SYSTEM ${LIBRTMP_INCLUDE_DIRS})
  link_directories(${LIBRTMP_LIBRARY_DIRS})
  if(LIBRTMP_CFLAGS)
    string(APPEND CMAKE_C_FLAGS " ${LIBRTMP_CFLAGS}")
  endif()
endif()

option(ENABLE_UNIX_SOCKETS "Enable Unix domain sockets support" ON)
if(ENABLE_UNIX_SOCKETS AND NOT WINCE)
  if(WIN32 OR DOS)
    set(USE_UNIX_SOCKETS 1)
  else()
    include(CheckStructHasMember)
    check_struct_has_member("struct sockaddr_un" "sun_path" "sys/un.h" USE_UNIX_SOCKETS)
  endif()
else()
  set(USE_UNIX_SOCKETS 0)
  unset(USE_UNIX_SOCKETS CACHE)
endif()

#
# CA handling
#
if(_curl_ca_bundle_supported)
  set(_ca_opt_desc "Set 'none' to disable or 'auto' for auto-detection. Defaults to 'auto'.")

  set(CURL_CA_BUNDLE "auto" CACHE
    STRING "Absolute path to the CA bundle. ${_ca_opt_desc}")
  set(CURL_CA_FALLBACK OFF CACHE
    BOOL "Use built-in CA store of OpenSSL. Defaults to OFF")
  set(CURL_CA_PATH "auto" CACHE
    STRING "Absolute path to a directory containing CA certificates stored individually. ${_ca_opt_desc}")
  set(CURL_CA_EMBED "" CACHE
    STRING "Absolute path to the CA bundle to embed in the curl tool.")

  if(CURL_CA_FALLBACK AND NOT CURL_USE_OPENSSL)
    message(FATAL_ERROR "CURL_CA_FALLBACK only works with OpenSSL.")
  endif()

  if(CURL_CA_BUNDLE STREQUAL "")
    message(FATAL_ERROR "Invalid value of CURL_CA_BUNDLE. Use 'none', 'auto' or file path.")
  elseif(CURL_CA_BUNDLE STREQUAL "none")
    unset(CURL_CA_BUNDLE CACHE)
  elseif(CURL_CA_BUNDLE STREQUAL "auto")
    unset(CURL_CA_BUNDLE CACHE)
    if(NOT CMAKE_CROSSCOMPILING AND NOT WIN32 AND NOT USE_APPLE_SECTRUST)
      set(_curl_ca_bundle_autodetect TRUE)
    endif()
  else()
    set(CURL_CA_BUNDLE_SET TRUE)
  endif()
  mark_as_advanced(CURL_CA_BUNDLE_SET)

  if(CURL_CA_PATH STREQUAL "")
    message(FATAL_ERROR "Invalid value of CURL_CA_PATH. Use 'none', 'auto' or directory path.")
  elseif(CURL_CA_PATH STREQUAL "none")
    unset(CURL_CA_PATH CACHE)
  elseif(CURL_CA_PATH STREQUAL "auto")
    unset(CURL_CA_PATH CACHE)
    if(NOT CMAKE_CROSSCOMPILING AND NOT WIN32)
      set(_curl_ca_path_autodetect TRUE)
    endif()
  else()
    set(CURL_CA_PATH_SET TRUE)
  endif()
  mark_as_advanced(CURL_CA_PATH_SET)

  if(CURL_CA_BUNDLE_SET AND _curl_ca_path_autodetect)
    # Skip auto-detection of unset CA path because CA bundle is set explicitly
  elseif(CURL_CA_PATH_SET AND _curl_ca_bundle_autodetect)
    # Skip auto-detection of unset CA bundle because CA path is set explicitly
  elseif(_curl_ca_bundle_autodetect OR _curl_ca_path_autodetect)
    # First try auto-detecting a CA bundle, then a CA path

    if(_curl_ca_bundle_autodetect)
      foreach(_search_ca_bundle_path IN ITEMS
          "/etc/ssl/certs/ca-certificates.crt"
          "/etc/pki/tls/certs/ca-bundle.crt"
          "/usr/share/ssl/certs/ca-bundle.crt"
          "/usr/local/share/certs/ca-root-nss.crt"
          "/etc/ssl/cert.pem")
        if(EXISTS "${_search_ca_bundle_path}")
          message(STATUS "Found CA bundle: ${_search_ca_bundle_path}")
          set(CURL_CA_BUNDLE "${_search_ca_bundle_path}" CACHE
            STRING "Absolute path to the CA bundle. ${_ca_opt_desc}")
          set(CURL_CA_BUNDLE_SET TRUE CACHE BOOL "Absolute path to the CA bundle has been set")
          break()
        endif()
      endforeach()
    endif()

    if(_curl_ca_path_autodetect AND NOT CURL_CA_PATH_SET)
      set(_search_ca_path "/etc/ssl/certs")
      file(GLOB _curl_ca_files_found "${_search_ca_path}/[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f].0")
      if(_curl_ca_files_found)
        unset(_curl_ca_files_found)
        message(STATUS "Found CA path: ${_search_ca_path}")
        set(CURL_CA_PATH "${_search_ca_path}" CACHE
          STRING "Absolute path to a directory containing CA certificates stored individually. ${_ca_opt_desc}")
        set(CURL_CA_PATH_SET TRUE CACHE BOOL "Absolute path to the CA bundle has been set")
      endif()
    endif()
  endif()

  set(CURL_CA_EMBED_SET FALSE)
  if(BUILD_CURL_EXE AND NOT CURL_CA_EMBED STREQUAL "")
    if(EXISTS "${CURL_CA_EMBED}")
      set(CURL_CA_EMBED_SET TRUE)
      message(STATUS "Found CA bundle to embed: ${CURL_CA_EMBED}")
    else()
      message(FATAL_ERROR "CA bundle to embed is missing: '${CURL_CA_EMBED}'")
    endif()
  endif()
endif()

if(WIN32)
  option(CURL_DISABLE_CA_SEARCH "Disable unsafe CA bundle search in PATH on Windows" OFF)
  option(CURL_CA_SEARCH_SAFE "Enable safe CA bundle search (within the curl tool directory) on Windows" OFF)
endif()

# Check for header files
if(WIN32)
  list(APPEND CURL_INCLUDES "winsock2.h")
  list(APPEND CURL_INCLUDES "ws2tcpip.h")

  if(HAVE_WIN32_WINNT AND HAVE_WIN32_WINNT LESS 0x0501 AND NOT WINCE)
    # Windows XP is required for freeaddrinfo, getaddrinfo
    message(FATAL_ERROR "Building for Windows XP or newer is required.")
  endif()

  # Pre-fill detection results based on target OS version
  if(_CURL_PREFILL)
    if(NOT HAVE_WIN32_WINNT OR HAVE_WIN32_WINNT LESS 0x0600 OR  # older than Windows Vista
       WINCE OR WINDOWS_STORE)
      set(HAVE_IF_NAMETOINDEX 0)
      unset(HAVE_IF_NAMETOINDEX CACHE)
    elseif(MSVC OR MINGW)
      set(HAVE_IF_NAMETOINDEX 1)
      unset(HAVE_IF_NAMETOINDEX CACHE)
    endif()
  endif()
endif()

if(NOT WIN32)
  list(APPEND CURL_INCLUDES "sys/socket.h")
endif()
if(NOT WIN32 OR MINGW)
  list(APPEND CURL_INCLUDES "sys/time.h")
endif()

# Detect headers

# Use check_include_file_concat_curl() for headers required by subsequent
# check_include_file_concat_curl() or check_symbol_exists() detections.
# Order for these is significant.
check_include_file("sys/eventfd.h"    HAVE_SYS_EVENTFD_H)
check_include_file("sys/filio.h"      HAVE_SYS_FILIO_H)
check_include_file("sys/ioctl.h"      HAVE_SYS_IOCTL_H)
check_include_file("sys/param.h"      HAVE_SYS_PARAM_H)
check_include_file("sys/poll.h"       HAVE_SYS_POLL_H)
check_include_file("sys/resource.h"   HAVE_SYS_RESOURCE_H)
check_include_file_concat_curl("sys/select.h"     HAVE_SYS_SELECT_H)
check_include_file("sys/sockio.h"     HAVE_SYS_SOCKIO_H)
check_include_file_concat_curl("sys/types.h"      HAVE_SYS_TYPES_H)
check_include_file("sys/un.h"         HAVE_SYS_UN_H)
check_include_file_concat_curl("sys/utime.h"      HAVE_SYS_UTIME_H)  # sys/types.h (AmigaOS)

check_include_file_concat_curl("arpa/inet.h"      HAVE_ARPA_INET_H)
check_include_file("dirent.h"         HAVE_DIRENT_H)
check_include_file("fcntl.h"          HAVE_FCNTL_H)
check_include_file_concat_curl("ifaddrs.h"        HAVE_IFADDRS_H)
check_include_file("io.h"             HAVE_IO_H)
check_include_file_concat_curl("libgen.h"         HAVE_LIBGEN_H)
check_include_file("linux/tcp.h"      HAVE_LINUX_TCP_H)
check_include_file("locale.h"         HAVE_LOCALE_H)
check_include_file_concat_curl("net/if.h"         HAVE_NET_IF_H)  # sys/select.h (e.g. MS-DOS/Watt-32)
check_include_file_concat_curl("netdb.h"          HAVE_NETDB_H)
check_include_file_concat_curl("netinet/in.h"     HAVE_NETINET_IN_H)
check_include_file("netinet/in6.h"    HAVE_NETINET_IN6_H)
check_include_file_concat_curl("netinet/tcp.h"    HAVE_NETINET_TCP_H)  # sys/types.h (e.g. Cygwin) netinet/in.h
check_include_file_concat_curl("netinet/udp.h"    HAVE_NETINET_UDP_H)  # sys/types.h (e.g. Cygwin)
check_include_file("poll.h"           HAVE_POLL_H)
check_include_file("pwd.h"            HAVE_PWD_H)
check_include_file("stdatomic.h"      HAVE_STDATOMIC_H)
check_include_file("stdbool.h"        HAVE_STDBOOL_H)
check_include_file("stdint.h"         HAVE_STDINT_H)
check_include_file("strings.h"        HAVE_STRINGS_H)
check_include_file("stropts.h"        HAVE_STROPTS_H)
check_include_file("termio.h"         HAVE_TERMIO_H)
check_include_file("termios.h"        HAVE_TERMIOS_H)
check_include_file_concat_curl("unistd.h"         HAVE_UNISTD_H)
check_include_file("utime.h"          HAVE_UTIME_H)

if(AMIGA)
  check_include_file_concat_curl("proto/bsdsocket.h" HAVE_PROTO_BSDSOCKET_H)
endif()

# Pass these detection results to curl_internal_test() for use in CurlTests.c
# Add here all feature flags referenced from CurlTests.c
foreach(_variable IN ITEMS
    HAVE_STDATOMIC_H
    HAVE_STDBOOL_H
    HAVE_STROPTS_H
    HAVE_SYS_IOCTL_H
    HAVE_SYS_TYPES_H
    HAVE_UNISTD_H
)
  if(${_variable})
    string(APPEND CURL_TEST_DEFINES " -D${_variable}")
  endif()
endforeach()

check_type_size("size_t"      SIZEOF_SIZE_T)
check_type_size("ssize_t"     SIZEOF_SSIZE_T)
check_type_size("long long"   SIZEOF_LONG_LONG)
check_type_size("long"        SIZEOF_LONG)
check_type_size("int"         SIZEOF_INT)
check_type_size("__int64"     SIZEOF___INT64)
check_type_size("time_t"      SIZEOF_TIME_T)
check_type_size("suseconds_t" SIZEOF_SUSECONDS_T)
if(NOT HAVE_SIZEOF_SSIZE_T)
  if(SIZEOF_LONG EQUAL SIZEOF_SIZE_T)
    set(ssize_t "long")
  endif()
  if(NOT ssize_t AND SIZEOF___INT64 EQUAL SIZEOF_SIZE_T)
    set(ssize_t "__int64")
  endif()
endif()
# off_t is sized later, after the HAVE_FILE_OFFSET_BITS test

if(SIZEOF_LONG_LONG)
  set(HAVE_LONGLONG 1)
endif()
if(SIZEOF_SUSECONDS_T)
  set(HAVE_SUSECONDS_T 1)
endif()

# Check for some functions that are used

# Apply to all feature checks
if(WIN32)
  list(APPEND CMAKE_REQUIRED_LIBRARIES "${_win32_winsock}")
  if(NOT WINCE AND NOT WINDOWS_STORE)
    list(APPEND CMAKE_REQUIRED_LIBRARIES "iphlpapi")
  endif()
elseif(HAVE_LIBSOCKET)
  list(APPEND CMAKE_REQUIRED_LIBRARIES "socket")
elseif(DOS)
  list(APPEND CMAKE_REQUIRED_LIBRARIES "${WATT_ROOT}/lib/libwatt.a")
endif()

check_function_exists("accept4"       HAVE_ACCEPT4)
check_function_exists("fnmatch"       HAVE_FNMATCH)
check_symbol_exists("basename"        "${CURL_INCLUDES};string.h" HAVE_BASENAME)  # libgen.h unistd.h
check_symbol_exists("opendir"         "dirent.h" HAVE_OPENDIR)
check_function_exists("poll"          HAVE_POLL)  # poll.h
check_symbol_exists("socket"          "${CURL_INCLUDES}" HAVE_SOCKET)  # winsock2.h sys/socket.h
check_symbol_exists("socketpair"      "${CURL_INCLUDES}" HAVE_SOCKETPAIR)  # sys/socket.h
check_symbol_exists("recv"            "${CURL_INCLUDES}" HAVE_RECV)  # proto/bsdsocket.h sys/types.h sys/socket.h
check_symbol_exists("send"            "${CURL_INCLUDES}" HAVE_SEND)  # proto/bsdsocket.h sys/types.h sys/socket.h
check_function_exists("sendmsg"       HAVE_SENDMSG)
check_function_exists("sendmmsg"      HAVE_SENDMMSG)
check_symbol_exists("select"          "${CURL_INCLUDES}" HAVE_SELECT)  # proto/bsdsocket.h sys/select.h sys/socket.h
check_symbol_exists("strdup"          "string.h" HAVE_STRDUP)
check_symbol_exists("memrchr"         "string.h" HAVE_MEMRCHR)
check_symbol_exists("alarm"           "unistd.h" HAVE_ALARM)
check_symbol_exists("fcntl"           "fcntl.h" HAVE_FCNTL)
check_function_exists("getppid"       HAVE_GETPPID)
check_function_exists("utimes"        HAVE_UTIMES)

check_function_exists("gettimeofday"  HAVE_GETTIMEOFDAY)  # sys/time.h
check_symbol_exists("closesocket"     "${CURL_INCLUDES}" HAVE_CLOSESOCKET)  # winsock2.h
check_symbol_exists("sigsetjmp"       "setjmp.h" HAVE_SIGSETJMP)
check_function_exists("getpass_r"     HAVE_GETPASS_R)
check_function_exists("getpwuid"      HAVE_GETPWUID)
check_function_exists("getpwuid_r"    HAVE_GETPWUID_R)
check_function_exists("geteuid"       HAVE_GETEUID)
check_function_exists("utime"         HAVE_UTIME)
check_symbol_exists("gmtime_r"        "stdlib.h;time.h" HAVE_GMTIME_R)

check_symbol_exists("gethostbyname_r" "netdb.h" HAVE_GETHOSTBYNAME_R)
check_symbol_exists("gethostname"     "${CURL_INCLUDES}" HAVE_GETHOSTNAME)  # winsock2.h unistd.h proto/bsdsocket.h

check_symbol_exists("signal"          "signal.h" HAVE_SIGNAL)
check_symbol_exists("strerror_r"      "stdlib.h;string.h" HAVE_STRERROR_R)
check_symbol_exists("sigaction"       "signal.h" HAVE_SIGACTION)
check_symbol_exists("siginterrupt"    "signal.h" HAVE_SIGINTERRUPT)
check_symbol_exists("getaddrinfo"     "${CURL_INCLUDES};stdlib.h;string.h" HAVE_GETADDRINFO)  # ws2tcpip.h sys/socket.h netdb.h
check_symbol_exists("getifaddrs"      "${CURL_INCLUDES};stdlib.h" HAVE_GETIFADDRS)  # ifaddrs.h
check_symbol_exists("freeaddrinfo"    "${CURL_INCLUDES}" HAVE_FREEADDRINFO)  # ws2tcpip.h sys/socket.h netdb.h
check_function_exists("pipe"          HAVE_PIPE)
check_function_exists("pipe2"         HAVE_PIPE2)
check_function_exists("eventfd"       HAVE_EVENTFD)
check_symbol_exists("ftruncate"       "unistd.h" HAVE_FTRUNCATE)
check_symbol_exists("getpeername"     "${CURL_INCLUDES}" HAVE_GETPEERNAME)  # winsock2.h unistd.h proto/bsdsocket.h
check_symbol_exists("getsockname"     "${CURL_INCLUDES}" HAVE_GETSOCKNAME)  # winsock2.h unistd.h proto/bsdsocket.h
check_function_exists("getrlimit"       HAVE_GETRLIMIT)
check_function_exists("setlocale"       HAVE_SETLOCALE)
check_function_exists("setrlimit"       HAVE_SETRLIMIT)

if(WIN32)
  # include wincrypt.h as a workaround for mingw-w64 __MINGW64_VERSION_MAJOR <= 5 header bug */
  check_symbol_exists("if_nametoindex"  "winsock2.h;wincrypt.h;iphlpapi.h" HAVE_IF_NAMETOINDEX)  # Windows Vista+ non-UWP */
else()
  check_function_exists("if_nametoindex"  HAVE_IF_NAMETOINDEX)  # net/if.h
  check_function_exists("realpath"        HAVE_REALPATH)
  check_function_exists("sched_yield"     HAVE_SCHED_YIELD)
  check_symbol_exists("strcasecmp"      "string.h" HAVE_STRCASECMP)
  check_symbol_exists("stricmp"         "string.h" HAVE_STRICMP)
  check_symbol_exists("strcmpi"         "string.h" HAVE_STRCMPI)
endif()

if(NOT MINGW32CE)  # Avoid false detections
  check_function_exists("setmode" HAVE_SETMODE)
  if(WIN32 OR CYGWIN)
    check_function_exists("_setmode" HAVE__SETMODE)
  endif()
endif()

if(AMIGA)
  check_symbol_exists("CloseSocket" "${CURL_INCLUDES}" HAVE_CLOSESOCKET_CAMEL)  # sys/socket.h proto/bsdsocket.h
endif()

if(NOT _ssl_enabled)
  check_symbol_exists("arc4random" "${CURL_INCLUDES};stdlib.h" HAVE_ARC4RANDOM)
endif()

if(NOT MSVC)
  check_function_exists("snprintf" HAVE_SNPRINTF)  # to match detection method in ./configure
elseif(MSVC_VERSION GREATER_EQUAL 1900)  # Earlier MSVC compilers had faulty snprintf implementations
  check_symbol_exists("snprintf" "stdio.h" HAVE_SNPRINTF)  # snprintf may be a compatibility macro, not an exported function
endif()
if(APPLE)
  check_function_exists("mach_absolute_time" HAVE_MACH_ABSOLUTE_TIME)
endif()
if(NOT WIN32)
  check_symbol_exists("inet_ntop" "${CURL_INCLUDES};stdlib.h;string.h" HAVE_INET_NTOP)  # arpa/inet.h netinet/in.h sys/socket.h
  check_symbol_exists("inet_pton" "${CURL_INCLUDES};stdlib.h;string.h" HAVE_INET_PTON)  # arpa/inet.h netinet/in.h sys/socket.h
endif()

check_symbol_exists("fsetxattr" "sys/xattr.h" HAVE_FSETXATTR)
if(HAVE_FSETXATTR)
  curl_internal_test(HAVE_FSETXATTR_5)
  curl_internal_test(HAVE_FSETXATTR_6)
endif()

cmake_push_check_state()
if(NOT WIN32)
  list(APPEND CMAKE_EXTRA_INCLUDE_FILES "sys/socket.h")
  check_type_size("sa_family_t" SIZEOF_SA_FAMILY_T)
  set(HAVE_SA_FAMILY_T ${HAVE_SIZEOF_SA_FAMILY_T})
endif()
cmake_pop_check_state()

# Do curl specific tests
foreach(_curl_test IN ITEMS
    HAVE_FCNTL_O_NONBLOCK
    HAVE_IOCTLSOCKET
    HAVE_IOCTLSOCKET_CAMEL
    HAVE_IOCTLSOCKET_CAMEL_FIONBIO
    HAVE_IOCTLSOCKET_FIONBIO
    HAVE_IOCTL_FIONBIO
    HAVE_IOCTL_SIOCGIFADDR
    HAVE_SETSOCKOPT_SO_NONBLOCK
    HAVE_GETHOSTBYNAME_R_3
    HAVE_GETHOSTBYNAME_R_5
    HAVE_GETHOSTBYNAME_R_6
    HAVE_BOOL_T
    STDC_HEADERS
    HAVE_ATOMIC
)
  curl_internal_test(${_curl_test})
endforeach()

# Check for reentrant
cmake_push_check_state()
list(APPEND CMAKE_REQUIRED_DEFINITIONS "-D_REENTRANT")
foreach(_curl_test IN ITEMS
    HAVE_GETHOSTBYNAME_R_3
    HAVE_GETHOSTBYNAME_R_5
    HAVE_GETHOSTBYNAME_R_6)
  curl_internal_test(${_curl_test}_REENTRANT)
  if(NOT ${_curl_test} AND ${_curl_test}_REENTRANT)
    set(NEED_REENTRANT 1)
  endif()
endforeach()
cmake_pop_check_state()

if(NEED_REENTRANT)
  foreach(_curl_test IN ITEMS
      HAVE_GETHOSTBYNAME_R_3
      HAVE_GETHOSTBYNAME_R_5
      HAVE_GETHOSTBYNAME_R_6)
    set(${_curl_test} 0)
    if(${_curl_test}_REENTRANT)
      set(${_curl_test} 1)
    endif()
  endforeach()
endif()

cmake_push_check_state()
list(APPEND CMAKE_REQUIRED_DEFINITIONS "-D_FILE_OFFSET_BITS=64")
curl_internal_test(HAVE_FILE_OFFSET_BITS)
cmake_pop_check_state()

cmake_push_check_state()
if(HAVE_FILE_OFFSET_BITS)
  set(_FILE_OFFSET_BITS 64)
  list(APPEND CMAKE_REQUIRED_DEFINITIONS "-D_FILE_OFFSET_BITS=64")
endif()
check_type_size("off_t" SIZEOF_OFF_T)

if(NOT WIN32)
  # fseeko may not exist with _FILE_OFFSET_BITS=64 but can exist with
  # _FILE_OFFSET_BITS unset or 32 (e.g. Android ARMv7 with NDK 26b and API level < 24)
  # so we need to test fseeko after testing for _FILE_OFFSET_BITS
  check_symbol_exists("fseeko" "${CURL_INCLUDES};stdio.h" HAVE_FSEEKO)

  if(HAVE_FSEEKO)
    set(HAVE_DECL_FSEEKO 1)
  endif()
endif()

# Include this header to get the type
cmake_push_check_state()
list(APPEND CMAKE_REQUIRED_INCLUDES "${SOURCE_ROOT}/include")
list(APPEND CMAKE_EXTRA_INCLUDE_FILES "curl/system.h")
check_type_size("curl_off_t" SIZEOF_CURL_OFF_T)
list(APPEND CMAKE_EXTRA_INCLUDE_FILES "curl/curl.h")
check_type_size("curl_socket_t" SIZEOF_CURL_SOCKET_T)
cmake_pop_check_state()  # pop curl system headers
cmake_pop_check_state()  # pop -D_FILE_OFFSET_BITS=64

if(NOT WIN32 AND NOT CMAKE_CROSSCOMPILING)
  # On non-Windows and not cross-compiling, check for writable argv[]
  include(CheckCSourceRuns)
  check_c_source_runs("
    int main(int argc, char **argv)
    {
      (void)argc;
      argv[0][0] = ' ';
      return (argv[0][0] == ' ')?0:1;
    }" HAVE_WRITABLE_ARGV)
endif()

# Fixed Windows cache already declares HAVE_TIME_T_UNSIGNED=0; no generated native probe execution.

curl_internal_test(HAVE_GLIBC_STRERROR_R)
curl_internal_test(HAVE_POSIX_STRERROR_R)

if(NOT WIN32)
  curl_internal_test(HAVE_CLOCK_GETTIME_MONOTONIC)  # Check clock_gettime(CLOCK_MONOTONIC, x) support
endif()

if(APPLE)
  curl_internal_test(HAVE_BUILTIN_AVAILABLE)  # Check compiler support of __builtin_available()
endif()

# Some other minor tests

if(_cmake_try_compile_target_type_save)
  set(CMAKE_TRY_COMPILE_TARGET_TYPE ${_cmake_try_compile_target_type_save})
  unset(_cmake_try_compile_target_type_save)
endif()

include("${SOURCE_ROOT}/CMake/OtherTests.cmake")

set_property(DIRECTORY APPEND PROPERTY COMPILE_DEFINITIONS "HAVE_CONFIG_H")

if(WIN32)
  list(APPEND CURL_NETWORK_AND_TIME_LIBS "${_win32_winsock}")
  if(NOT WINCE AND NOT WINDOWS_STORE)
    list(APPEND CURL_NETWORK_AND_TIME_LIBS "iphlpapi")
  endif()
  if(NOT WINCE)
    list(APPEND CURL_LIBS "bcrypt")
  endif()

  if(NOT WINCE)
    set(USE_WIN32_LARGE_FILES ON)
  endif()

  # We use crypto functions that are not available for UWP apps
  if(NOT WINDOWS_STORE)
    set(USE_WIN32_CRYPTO ON)
  endif()

  # Link required libraries for USE_WIN32_CRYPTO or USE_SCHANNEL
  if(USE_WIN32_CRYPTO OR USE_SCHANNEL)
    if(NOT WINCE)
      list(APPEND CURL_LIBS "advapi32")
    endif()
    list(APPEND CURL_LIBS "${_win32_crypt32}")
  endif()
  if(USE_WINDOWS_SSPI)
    list(APPEND CURL_LIBS "${_win32_secur32}")
  endif()
endif()

list(APPEND CURL_LIBS ${CURL_NETWORK_AND_TIME_LIBS})
if(CURL_CODE_COVERAGE)
  list(APPEND CURL_LIBS ${CURL_COVERAGE_LIBS})
endif()

if(CMAKE_C_COMPILER_ID STREQUAL "MSVC")  # MSVC but exclude clang-cl
  set_property(DIRECTORY APPEND PROPERTY COMPILE_OPTIONS "-MP")  # Parallel compilation
endif()

if(CURL_LTO)
  if(CMAKE_VERSION VERSION_LESS 3.9)
    message(FATAL_ERROR "LTO has been requested, but your cmake version ${CMAKE_VERSION} is to old. You need at least 3.9")
  endif()

  cmake_policy(SET CMP0069 NEW)

  include(CheckIPOSupported)
  check_ipo_supported(RESULT CURL_HAS_LTO OUTPUT _lto_error LANGUAGES C)
  if(CURL_HAS_LTO)
    message(STATUS "LTO supported and enabled")
  else()
    message(FATAL_ERROR "LTO has been requested, but the compiler does not support it\n${_lto_error}")
  endif()
endif()


""",
    'curl-macros': r"""#***************************************************************************
#                                  _   _ ____  _
#  Project                     ___| | | |  _ \| |
#                             / __| | | | |_) | |
#                            | (__| |_| |  _ <| |___
#                             \___|\___/|_| \_\_____|
#
# Copyright (C) Daniel Stenberg, <daniel@haxx.se>, et al.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at https://curl.se/docs/copyright.html.
#
# You may opt to use, copy, modify, merge, publish, distribute and/or sell
# copies of the Software, and permit persons to whom the Software is
# furnished to do so, under the terms of the COPYING file.
#
# This software is distributed on an "AS IS" basis, WITHOUT WARRANTY OF ANY
# KIND, either express or implied.
#
# SPDX-License-Identifier: curl
#
###########################################################################
# File defines convenience macros for available feature testing

# Check if header file exists and add it to the list.
# This macro is intended to be called multiple times with a sequence of
# possibly dependent header files.  Some headers depend on others to be
# compiled correctly.
macro(check_include_file_concat_curl _file _variable)
  check_include_files("${CURL_INCLUDES};${_file}" ${_variable})
  if(${_variable})
    list(APPEND CURL_INCLUDES ${_file})
  endif()
endmacro()

set(CURL_TEST_DEFINES "")  # Initialize global variable

# For other curl specific tests, use this macro.
# Return result in variable: CURL_TEST_OUTPUT
macro(curl_internal_test _curl_test)
  if(NOT DEFINED "${_curl_test}")
    string(REPLACE ";" " " _cmake_required_definitions "${CMAKE_REQUIRED_DEFINITIONS}")
    set(_curl_test_add_libraries "")
    if(CMAKE_REQUIRED_LIBRARIES)
      set(_curl_test_add_libraries
        "-DLINK_LIBRARIES:STRING=${CMAKE_REQUIRED_LIBRARIES}")
    endif()

    message(STATUS "Performing Test ${_curl_test}")
    try_compile(${_curl_test}
      ${PROJECT_BINARY_DIR}
      "${SOURCE_ROOT}/CMake/CurlTests.c"
      CMAKE_FLAGS
        "-DCOMPILE_DEFINITIONS:STRING=-D${_curl_test} ${CURL_TEST_DEFINES} ${CMAKE_REQUIRED_FLAGS} ${_cmake_required_definitions}"
        "${_curl_test_add_libraries}"
      OUTPUT_VARIABLE CURL_TEST_OUTPUT)
    if(${_curl_test})
      set(${_curl_test} 1 CACHE INTERNAL "Curl test")
      message(STATUS "Performing Test ${_curl_test} - Success")
    else()
      set(${_curl_test} "" CACHE INTERNAL "Curl test")
      message(STATUS "Performing Test ${_curl_test} - Failed")
    endif()
  endif()
endmacro()

# Option for dependencies that accepts an 'AUTO' value, which enables the dependency if detected.
macro(curl_dependency_option _option_name _find_name _desc_name)
  set(${_option_name} "AUTO" CACHE STRING "Build curl with ${_desc_name} support (AUTO, ON or OFF)")
  set_property(CACHE ${_option_name} PROPERTY STRINGS "AUTO" "ON" "OFF")

  if(${_option_name} STREQUAL "AUTO")
    find_package(${_find_name})
  elseif(${_option_name})
    find_package(${_find_name} REQUIRED)
  endif()
endmacro()

# Convert the passed paths to libpath linker options and add them to CMAKE_REQUIRED_*.
macro(curl_required_libpaths _libpaths_arg)
  if(CMAKE_VERSION VERSION_LESS 3.31)
    set(_libpaths "${_libpaths_arg}")
    foreach(_libpath IN LISTS _libpaths)
      list(APPEND CMAKE_REQUIRED_LINK_OPTIONS "${CMAKE_LIBRARY_PATH_FLAG}${_libpath}")
    endforeach()
  else()
    list(APPEND CMAKE_REQUIRED_LINK_DIRECTORIES "${_libpaths_arg}")
  endif()
endmacro()

# Pre-fill variables set by a check_type_size() call.
macro(curl_prefill_type_size _type _size)
  set(HAVE_SIZEOF_${_type} TRUE)
  set(SIZEOF_${_type} ${_size})
  set(SIZEOF_${_type}_CODE "#define SIZEOF_${_type} ${_size}")
endmacro()

# Internal: Recurse into target libraries and collect their include directories
# and macro definitions.
macro(curl_collect_target_options _target)
  get_target_property(_val ${_target} INTERFACE_INCLUDE_DIRECTORIES)
  if(_val)
    list(APPEND _includes ${_val})
  endif()
  get_target_property(_val ${_target} INCLUDE_DIRECTORIES)
  if(_val)
    list(APPEND _includes ${_val})
  endif()
  get_target_property(_val ${_target} COMPILE_DEFINITIONS)
  if(_val)
    list(APPEND _definitions ${_val})
  endif()
  get_target_property(_val ${_target} LINK_LIBRARIES)
  if(_val)
    foreach(_lib IN LISTS _val)
      if(TARGET "${_lib}")
        curl_collect_target_options(${_lib})
      endif()
    endforeach()
  endif()
  unset(_val)
endmacro()

# Create a clang-tidy target for test targets
macro(curl_add_clang_tidy_test_target _target_clang_tidy _target)
  if(CURL_CLANG_TIDY)

    set(_includes "")
    set(_definitions "")

    # Collect header directories and macro definitions applying to the directory
    get_directory_property(_val INCLUDE_DIRECTORIES)
    if(_val)
      list(APPEND _includes ${_val})
    endif()
    get_directory_property(_val COMPILE_DEFINITIONS)
    if(_val)
      list(APPEND _definitions ${_val})
    endif()
    unset(_val)

    # Collect header directories and macro definitions from lib dependencies
    curl_collect_target_options(${_target})

    list(REMOVE_ITEM _includes "")
    string(REPLACE ";" ";-I" _includes ";${_includes}")
    list(REMOVE_DUPLICATES _includes)

    list(REMOVE_ITEM _definitions "")
    string(REPLACE ";" ";-D" _definitions ";${_definitions}")
    list(REMOVE_DUPLICATES _definitions)
    list(SORT _definitions)  # Sort like CMake does

    # Assemble source list
    set(_sources "")
    foreach(_source IN ITEMS ${ARGN})
      if(NOT EXISTS "${SOURCE_ROOT}/${_source}")  # if not in source tree
        set(_source "${CMAKE_CURRENT_BINARY_DIR}/${_source}")  # look in the build tree, for generated files, e.g. lib1521.c
      endif()
      list(APPEND _sources "${_source}")
    endforeach()

    add_custom_target(${_target_clang_tidy} USES_TERMINAL
      WORKING_DIRECTORY "${SOURCE_ROOT}"
      COMMAND ${CMAKE_C_CLANG_TIDY} ${_sources} -- ${_includes} ${_definitions}
      DEPENDS ${_sources})
    add_dependencies(tests-clang-tidy ${_target_clang_tidy})

    unset(_includes)
    unset(_definitions)
    unset(_sources)
  endif()
endmacro()
""",
    'curl-library': r"""# Reviewed lib/CMakeLists.txt static branch and Makefile.inc.
file(MAKE_DIRECTORY "${PROJECT_BINARY_DIR}/lib")
configure_file("${SOURCE_ROOT}/lib/curl_config.h.cmake" "${PROJECT_BINARY_DIR}/lib/curl_config.h")
add_library(libcurl_static STATIC
  "${SOURCE_ROOT}/lib/altsvc.c"
  "${SOURCE_ROOT}/lib/amigaos.c"
  "${SOURCE_ROOT}/lib/asyn-ares.c"
  "${SOURCE_ROOT}/lib/asyn-base.c"
  "${SOURCE_ROOT}/lib/asyn-thrdd.c"
  "${SOURCE_ROOT}/lib/bufq.c"
  "${SOURCE_ROOT}/lib/bufref.c"
  "${SOURCE_ROOT}/lib/cf-h1-proxy.c"
  "${SOURCE_ROOT}/lib/cf-h2-proxy.c"
  "${SOURCE_ROOT}/lib/cf-haproxy.c"
  "${SOURCE_ROOT}/lib/cf-https-connect.c"
  "${SOURCE_ROOT}/lib/cf-ip-happy.c"
  "${SOURCE_ROOT}/lib/cf-socket.c"
  "${SOURCE_ROOT}/lib/cfilters.c"
  "${SOURCE_ROOT}/lib/conncache.c"
  "${SOURCE_ROOT}/lib/connect.c"
  "${SOURCE_ROOT}/lib/content_encoding.c"
  "${SOURCE_ROOT}/lib/cookie.c"
  "${SOURCE_ROOT}/lib/cshutdn.c"
  "${SOURCE_ROOT}/lib/curl_addrinfo.c"
  "${SOURCE_ROOT}/lib/curl_endian.c"
  "${SOURCE_ROOT}/lib/curl_fnmatch.c"
  "${SOURCE_ROOT}/lib/curl_fopen.c"
  "${SOURCE_ROOT}/lib/curl_get_line.c"
  "${SOURCE_ROOT}/lib/curl_gethostname.c"
  "${SOURCE_ROOT}/lib/curl_gssapi.c"
  "${SOURCE_ROOT}/lib/curl_memrchr.c"
  "${SOURCE_ROOT}/lib/curl_ntlm_core.c"
  "${SOURCE_ROOT}/lib/curl_range.c"
  "${SOURCE_ROOT}/lib/curl_rtmp.c"
  "${SOURCE_ROOT}/lib/curl_sasl.c"
  "${SOURCE_ROOT}/lib/curl_sha512_256.c"
  "${SOURCE_ROOT}/lib/curl_sspi.c"
  "${SOURCE_ROOT}/lib/curl_threads.c"
  "${SOURCE_ROOT}/lib/curl_trc.c"
  "${SOURCE_ROOT}/lib/cw-out.c"
  "${SOURCE_ROOT}/lib/cw-pause.c"
  "${SOURCE_ROOT}/lib/dict.c"
  "${SOURCE_ROOT}/lib/doh.c"
  "${SOURCE_ROOT}/lib/dynhds.c"
  "${SOURCE_ROOT}/lib/easy.c"
  "${SOURCE_ROOT}/lib/easygetopt.c"
  "${SOURCE_ROOT}/lib/easyoptions.c"
  "${SOURCE_ROOT}/lib/escape.c"
  "${SOURCE_ROOT}/lib/fake_addrinfo.c"
  "${SOURCE_ROOT}/lib/file.c"
  "${SOURCE_ROOT}/lib/fileinfo.c"
  "${SOURCE_ROOT}/lib/formdata.c"
  "${SOURCE_ROOT}/lib/ftp.c"
  "${SOURCE_ROOT}/lib/ftplistparser.c"
  "${SOURCE_ROOT}/lib/getenv.c"
  "${SOURCE_ROOT}/lib/getinfo.c"
  "${SOURCE_ROOT}/lib/gopher.c"
  "${SOURCE_ROOT}/lib/hash.c"
  "${SOURCE_ROOT}/lib/headers.c"
  "${SOURCE_ROOT}/lib/hmac.c"
  "${SOURCE_ROOT}/lib/hostip.c"
  "${SOURCE_ROOT}/lib/hostip4.c"
  "${SOURCE_ROOT}/lib/hostip6.c"
  "${SOURCE_ROOT}/lib/hsts.c"
  "${SOURCE_ROOT}/lib/http.c"
  "${SOURCE_ROOT}/lib/http1.c"
  "${SOURCE_ROOT}/lib/http2.c"
  "${SOURCE_ROOT}/lib/http_aws_sigv4.c"
  "${SOURCE_ROOT}/lib/http_chunks.c"
  "${SOURCE_ROOT}/lib/http_digest.c"
  "${SOURCE_ROOT}/lib/http_negotiate.c"
  "${SOURCE_ROOT}/lib/http_ntlm.c"
  "${SOURCE_ROOT}/lib/http_proxy.c"
  "${SOURCE_ROOT}/lib/httpsrr.c"
  "${SOURCE_ROOT}/lib/idn.c"
  "${SOURCE_ROOT}/lib/if2ip.c"
  "${SOURCE_ROOT}/lib/imap.c"
  "${SOURCE_ROOT}/lib/ldap.c"
  "${SOURCE_ROOT}/lib/llist.c"
  "${SOURCE_ROOT}/lib/macos.c"
  "${SOURCE_ROOT}/lib/md4.c"
  "${SOURCE_ROOT}/lib/md5.c"
  "${SOURCE_ROOT}/lib/memdebug.c"
  "${SOURCE_ROOT}/lib/mime.c"
  "${SOURCE_ROOT}/lib/mprintf.c"
  "${SOURCE_ROOT}/lib/mqtt.c"
  "${SOURCE_ROOT}/lib/multi.c"
  "${SOURCE_ROOT}/lib/multi_ev.c"
  "${SOURCE_ROOT}/lib/multi_ntfy.c"
  "${SOURCE_ROOT}/lib/netrc.c"
  "${SOURCE_ROOT}/lib/noproxy.c"
  "${SOURCE_ROOT}/lib/openldap.c"
  "${SOURCE_ROOT}/lib/parsedate.c"
  "${SOURCE_ROOT}/lib/pingpong.c"
  "${SOURCE_ROOT}/lib/pop3.c"
  "${SOURCE_ROOT}/lib/progress.c"
  "${SOURCE_ROOT}/lib/psl.c"
  "${SOURCE_ROOT}/lib/rand.c"
  "${SOURCE_ROOT}/lib/rename.c"
  "${SOURCE_ROOT}/lib/request.c"
  "${SOURCE_ROOT}/lib/rtsp.c"
  "${SOURCE_ROOT}/lib/select.c"
  "${SOURCE_ROOT}/lib/sendf.c"
  "${SOURCE_ROOT}/lib/setopt.c"
  "${SOURCE_ROOT}/lib/sha256.c"
  "${SOURCE_ROOT}/lib/share.c"
  "${SOURCE_ROOT}/lib/slist.c"
  "${SOURCE_ROOT}/lib/smb.c"
  "${SOURCE_ROOT}/lib/smtp.c"
  "${SOURCE_ROOT}/lib/socketpair.c"
  "${SOURCE_ROOT}/lib/socks.c"
  "${SOURCE_ROOT}/lib/socks_gssapi.c"
  "${SOURCE_ROOT}/lib/socks_sspi.c"
  "${SOURCE_ROOT}/lib/speedcheck.c"
  "${SOURCE_ROOT}/lib/splay.c"
  "${SOURCE_ROOT}/lib/strcase.c"
  "${SOURCE_ROOT}/lib/strdup.c"
  "${SOURCE_ROOT}/lib/strequal.c"
  "${SOURCE_ROOT}/lib/strerror.c"
  "${SOURCE_ROOT}/lib/system_win32.c"
  "${SOURCE_ROOT}/lib/telnet.c"
  "${SOURCE_ROOT}/lib/tftp.c"
  "${SOURCE_ROOT}/lib/transfer.c"
  "${SOURCE_ROOT}/lib/uint-bset.c"
  "${SOURCE_ROOT}/lib/uint-hash.c"
  "${SOURCE_ROOT}/lib/uint-spbset.c"
  "${SOURCE_ROOT}/lib/uint-table.c"
  "${SOURCE_ROOT}/lib/url.c"
  "${SOURCE_ROOT}/lib/urlapi.c"
  "${SOURCE_ROOT}/lib/version.c"
  "${SOURCE_ROOT}/lib/ws.c"
  "${SOURCE_ROOT}/lib/vauth/cleartext.c"
  "${SOURCE_ROOT}/lib/vauth/cram.c"
  "${SOURCE_ROOT}/lib/vauth/digest.c"
  "${SOURCE_ROOT}/lib/vauth/digest_sspi.c"
  "${SOURCE_ROOT}/lib/vauth/gsasl.c"
  "${SOURCE_ROOT}/lib/vauth/krb5_gssapi.c"
  "${SOURCE_ROOT}/lib/vauth/krb5_sspi.c"
  "${SOURCE_ROOT}/lib/vauth/ntlm.c"
  "${SOURCE_ROOT}/lib/vauth/ntlm_sspi.c"
  "${SOURCE_ROOT}/lib/vauth/oauth2.c"
  "${SOURCE_ROOT}/lib/vauth/spnego_gssapi.c"
  "${SOURCE_ROOT}/lib/vauth/spnego_sspi.c"
  "${SOURCE_ROOT}/lib/vauth/vauth.c"
  "${SOURCE_ROOT}/lib/vtls/apple.c"
  "${SOURCE_ROOT}/lib/vtls/cipher_suite.c"
  "${SOURCE_ROOT}/lib/vtls/gtls.c"
  "${SOURCE_ROOT}/lib/vtls/hostcheck.c"
  "${SOURCE_ROOT}/lib/vtls/keylog.c"
  "${SOURCE_ROOT}/lib/vtls/mbedtls.c"
  "${SOURCE_ROOT}/lib/vtls/mbedtls_threadlock.c"
  "${SOURCE_ROOT}/lib/vtls/openssl.c"
  "${SOURCE_ROOT}/lib/vtls/rustls.c"
  "${SOURCE_ROOT}/lib/vtls/schannel.c"
  "${SOURCE_ROOT}/lib/vtls/schannel_verify.c"
  "${SOURCE_ROOT}/lib/vtls/vtls.c"
  "${SOURCE_ROOT}/lib/vtls/vtls_scache.c"
  "${SOURCE_ROOT}/lib/vtls/vtls_spack.c"
  "${SOURCE_ROOT}/lib/vtls/wolfssl.c"
  "${SOURCE_ROOT}/lib/vtls/x509asn1.c"
  "${SOURCE_ROOT}/lib/vquic/curl_ngtcp2.c"
  "${SOURCE_ROOT}/lib/vquic/curl_osslq.c"
  "${SOURCE_ROOT}/lib/vquic/curl_quiche.c"
  "${SOURCE_ROOT}/lib/vquic/vquic.c"
  "${SOURCE_ROOT}/lib/vquic/vquic-tls.c"
  "${SOURCE_ROOT}/lib/vssh/libssh.c"
  "${SOURCE_ROOT}/lib/vssh/libssh2.c"
  "${SOURCE_ROOT}/lib/vssh/curl_path.c"
  "${SOURCE_ROOT}/lib/curlx/base64.c"
  "${SOURCE_ROOT}/lib/curlx/dynbuf.c"
  "${SOURCE_ROOT}/lib/curlx/fopen.c"
  "${SOURCE_ROOT}/lib/curlx/inet_ntop.c"
  "${SOURCE_ROOT}/lib/curlx/inet_pton.c"
  "${SOURCE_ROOT}/lib/curlx/multibyte.c"
  "${SOURCE_ROOT}/lib/curlx/nonblock.c"
  "${SOURCE_ROOT}/lib/curlx/strerr.c"
  "${SOURCE_ROOT}/lib/curlx/strparse.c"
  "${SOURCE_ROOT}/lib/curlx/timediff.c"
  "${SOURCE_ROOT}/lib/curlx/timeval.c"
  "${SOURCE_ROOT}/lib/curlx/version_win32.c"
  "${SOURCE_ROOT}/lib/curlx/wait.c"
  "${SOURCE_ROOT}/lib/curlx/warnless.c"
  "${SOURCE_ROOT}/lib/curlx/winapi.c"
)
target_include_directories(libcurl_static PRIVATE "${SOURCE_ROOT}/include" "${SOURCE_ROOT}/lib" "${PROJECT_BINARY_DIR}/lib")
target_compile_definitions(libcurl_static PRIVATE BUILDING_LIBCURL HAVE_CONFIG_H PUBLIC CURL_STATICLIB)
target_link_libraries(libcurl_static PRIVATE ${CURL_LIBS})
set_target_properties(libcurl_static PROPERTIES PREFIX "" OUTPUT_NAME "libcurl" SUFFIX ".lib" DEBUG_POSTFIX "" MSVC_RUNTIME_LIBRARY "MultiThreaded")
install(TARGETS libcurl_static ARCHIVE DESTINATION lib)
install(DIRECTORY "${SOURCE_ROOT}/include/curl" DESTINATION include FILES_MATCHING PATTERN "*.h")
""",
}

# Parent-approved owned publication destinations. These are not observations of
# upstream output names; each producer independently owns its exact install map.
# No caller supplies or overrides this table.
PREFIX_LIBRARIES = {
    'ICU::data': 'lib/icudata.lib',
    'ICU::uc': 'lib/icuuc.lib',
    'ICU::i18n': 'lib/icui18n.lib',
    'OpenSSL::SSL': 'lib/libssl.lib',
    'OpenSSL::Crypto': 'lib/libcrypto.lib',
    'LibPSL::LibPSL': 'lib/psl.lib',
    'ZLIB::ZLIB': 'lib/zlibstatic.lib',
    'Brotli::common': 'lib/brotlicommon.lib',
    'Brotli::dec': 'lib/brotlidec.lib',
    'FoundationNative::nghttp2': 'lib/nghttp2.lib',
}

# Still a real source prerequisite until the PSL owner supplies the exact
# reviewed header/static/system-link policy. Empty is different from unknown.
PSL_COMPILE_DEFINITIONS = None
PSL_SYSTEM_LINKS = None

OUTPUT_LIBRARIES = {
    'harfbuzz': {'HarfBuzz::HarfBuzz': 'lib/harfbuzz.lib',
                 'HarfBuzz::ICU': 'lib/harfbuzz-icu.lib'},
    'xml2': {'LibXml2::LibXml2': 'lib/libxml2s.lib'},
    'nghttp2': {'FoundationNative::nghttp2': 'lib/nghttp2.lib'},
    'curl': {'CURL::libcurl': 'lib/libcurl.lib'},
}

OPTIONS = {
    'harfbuzz': {
        'BUILD_FRAMEWORK': False, 'HB_HAVE_CAIRO': False,
        'HB_HAVE_FREETYPE': False, 'HB_HAVE_GRAPHITE2': False,
        'HB_HAVE_GLIB': False, 'HB_HAVE_ICU': True, 'HB_HAVE_CORETEXT': False,
        'HB_HAVE_UNISCRIBE': False, 'HB_HAVE_GDI': False,
        'HB_HAVE_DIRECTWRITE': False, 'HB_BUILD_UTILS': False,
        'HB_BUILD_SUBSET': False, 'HB_HAVE_GOBJECT': False,
        'HB_HAVE_INTROSPECTION': False,
    },
    'xml2': {
        'LIBXML2_WITH_ICU': True, 'LIBXML2_WITH_ZLIB': True,
        'LIBXML2_WITH_ICONV': False, 'LIBXML2_WITH_LZMA': False,
        'LIBXML2_WITH_MODULES': False, 'LIBXML2_WITH_PROGRAMS': False,
        'LIBXML2_WITH_PYTHON': False, 'LIBXML2_WITH_TESTS': False,
        'LIBXML2_WITH_THREADS': True, 'LIBXML2_WITH_THREAD_ALLOC': False,
        'LIBXML2_WITH_TLS': False, 'LIBXML2_WITH_SAX1': True,
    },
    'nghttp2': {
        'ENABLE_LIB_ONLY': True, 'BUILD_STATIC_LIBS': True,
        'ENABLE_STATIC_CRT': True, 'ENABLE_APP': False,
        'ENABLE_HPACK_TOOLS': False, 'ENABLE_EXAMPLES': False,
        'ENABLE_FAILMALLOC': False, 'ENABLE_DOC': False,
        'BUILD_TESTING': False, 'ENABLE_HTTP3': False,
        'WITH_LIBXML2': False, 'WITH_JEMALLOC': False,
        'WITH_MRUBY': False, 'WITH_NEVERBLEED': False,
        'WITH_LIBBPF': False, 'WITH_WOLFSSL': False,
    },
    'curl': {
        'BUILD_STATIC_LIBS': True, 'BUILD_STATIC_CURL': True,
        'CURL_STATIC_CRT': True, 'BUILD_CURL_EXE': False,
        'BUILD_TESTING': False, 'BUILD_EXAMPLES': False,
        'BUILD_LIBCURL_DOCS': False, 'BUILD_MISC_DOCS': False,
        'ENABLE_CURL_MANUAL': False, 'CURL_CLANG_TIDY': False,
        'CURL_CODE_COVERAGE': False, 'CURL_LTO': False,
        'PICKY_COMPILER': False, 'CURL_DISABLE_INSTALL': True,
        'CURL_ENABLE_SSL': True, 'CURL_USE_OPENSSL': True,
        'CURL_USE_SCHANNEL': False, 'CURL_WINDOWS_SSPI': False,
        'CURL_USE_MBEDTLS': False, 'CURL_USE_WOLFSSL': False,
        'CURL_USE_GNUTLS': False, 'CURL_USE_RUSTLS': False,
        'USE_APPLE_SECTRUST': False, 'CURL_ZLIB': True,
        'CURL_BROTLI': True, 'CURL_ZSTD': False, 'USE_NGHTTP2': True,
        'CURL_USE_LIBPSL': True, 'USE_LIBIDN2': False,
        'CURL_USE_LIBSSH2': False, 'CURL_USE_LIBSSH': False,
        'USE_LIBRTMP': False, 'CURL_DISABLE_LDAP': True,
        'CURL_DISABLE_LDAPS': True, 'CURL_USE_GSASL': False,
        'CURL_USE_GSSAPI': False, 'CURL_USE_LIBUV': False,
        'ENABLE_ARES': False, 'USE_NGTCP2': False, 'USE_QUICHE': False,
        'USE_OPENSSL_QUIC': False, 'USE_HTTPSRR': False, 'USE_ECH': False,
        'ENABLE_THREADED_RESOLVER': True, 'CURL_USE_PKGCONFIG': False,
        'CURL_CA_FALLBACK': False,
    },
}


def _literal(value):
    # These paths are already canonical Context data. Bracket arguments avoid
    # CMake interpolation. The common renderer also enforces its path domain.
    if type(value) is not str or not value.isascii() or ']=]' in value:
        raise ValueError('Representable fixed CMake path required')
    return '[=[' + value + ']=]'


def _selected_sources(context):
    supplier = context['supplier']
    files = context['source_layout']['files']
    if context['source_recipe_bindings']['source'] != SOURCES[supplier]:
        raise ValueError('Fixed original supplier identity differs')
    recipes = context['source_recipe_bindings']['recipes']
    if set(recipes) not in (set(), {'toolchain.cmake', 'initial-cache.cmake'}):
        raise ValueError('No arbitrary extra recipe is admitted')
    required = set(REQUIRED_MEMBERS[supplier])
    if supplier == 'curl':
        headers = sorted(name for name in files
                         if name.startswith('include/curl/') and name.endswith('.h'))
        if not headers:
            raise _factory.MissingInputs(['curl-public-headers-data'])
        required.update(headers)
    else:
        headers = list(PUBLIC_HEADERS[supplier])
    if any(member not in files for member in required):
        raise _factory.MissingInputs([supplier + '-selected-source-data'])
    for member, expected in REVIEWED_INPUTS[supplier].items():
        if files[member] != expected:
            raise ValueError('Reviewed original recipe/input pin differs: ' + member)
    selected = [dict(member=name, **files[name]) for name in sorted(required)]
    if supplier == 'harfbuzz':
        installed = ['include/harfbuzz/' + name.rsplit('/', 1)[-1] for name in headers]
        installed.append('include/harfbuzz/hb-features.h')
    elif supplier == 'xml2':
        installed = ['include/libxml2/libxml/' + name.rsplit('/', 1)[-1] for name in headers]
        installed.append('include/libxml2/libxml/xmlversion.h')
    elif supplier == 'nghttp2':
        installed = ['include/nghttp2/nghttp2.h', 'include/nghttp2/nghttp2ver.h']
    else:
        installed = headers
    return selected, sorted(set(installed))


def _imported(target, member, *, definitions=(), links=()):
    if type(member) is not str or not member.startswith('lib/') or not member.endswith('.lib'):
        raise ValueError('Fixed prefix archive member required')
    lines = ['add_library(' + target + ' STATIC IMPORTED GLOBAL)',
             'set_target_properties(' + target + ' PROPERTIES',
             '  IMPORTED_LOCATION "${PREFIX_ROOT}/' + member + '"',
             '  INTERFACE_INCLUDE_DIRECTORIES "${PREFIX_ROOT}/include"']
    if definitions:
        lines.append('  INTERFACE_COMPILE_DEFINITIONS "' + ';'.join(definitions) + '"')
    if links:
        lines.append('  INTERFACE_LINK_LIBRARIES "' + ';'.join(links) + '"')
    return '\n'.join(lines) + ')\n'


def _dependency_modules(supplier):
    if supplier in ('harfbuzz', 'xml2'):
        names = ('ICU::data', 'ICU::uc', 'ICU::i18n')
    elif supplier == 'curl':
        names = ('OpenSSL::Crypto', 'OpenSSL::SSL', 'LibPSL::LibPSL',
                 'ZLIB::ZLIB', 'Brotli::common', 'Brotli::dec',
                 'FoundationNative::nghttp2')
    else:
        return {}
    if any(name not in PREFIX_LIBRARIES for name in names):
        raise _factory.MissingInputs([supplier + '-predecessor-prefix-source-policy'])
    # Filled below only from fixed released cross-supplier target policy.
    return _released_dependency_modules(supplier)


def _released_dependency_modules(supplier):
    modules = {}
    if supplier in ('harfbuzz', 'xml2'):
        text = _imported('ICU::data', PREFIX_LIBRARIES['ICU::data'],
                         definitions=('U_STATIC_IMPLEMENTATION',))
        text += _imported('ICU::uc', PREFIX_LIBRARIES['ICU::uc'],
                          definitions=('U_STATIC_IMPLEMENTATION',), links=('ICU::data',))
        text += _imported('ICU::i18n', PREFIX_LIBRARIES['ICU::i18n'],
                          definitions=('U_STATIC_IMPLEMENTATION',), links=('ICU::uc', 'ICU::data'))
        text += 'set(ICU_FOUND TRUE)\nset(ICU_VERSION "77.1")\n'
        text += 'set(ICU_INCLUDE_DIRS "${PREFIX_ROOT}/include")\n'
        for component in ('data', 'uc', 'i18n'):
            text += 'set(ICU_' + component + '_FOUND TRUE)\n'
        modules['FindICU.cmake'] = text
    if supplier in ('xml2', 'curl'):
        text = _imported('ZLIB::ZLIB', PREFIX_LIBRARIES['ZLIB::ZLIB'])
        text += 'set(ZLIB_FOUND TRUE)\nset(ZLIB_VERSION "1.3.1")\nset(ZLIB_VERSION_STRING "1.3.1")\nset(ZLIB_VERSION_MAJOR 1)\n'
        modules['FindZLIB.cmake'] = text
    if supplier == 'curl':
        if PSL_COMPILE_DEFINITIONS is None or PSL_SYSTEM_LINKS is None:
            raise _factory.MissingInputs(['curl-psl-static-link-source-policy'])
        text = _imported('OpenSSL::Crypto', PREFIX_LIBRARIES['OpenSSL::Crypto'])
        text += _imported('OpenSSL::SSL', PREFIX_LIBRARIES['OpenSSL::SSL'], links=('OpenSSL::Crypto',))
        text += 'set(OPENSSL_FOUND TRUE)\nset(OpenSSL_FOUND TRUE)\nset(OPENSSL_USE_STATIC_LIBS TRUE)\nset(OPENSSL_MSVC_STATIC_RT TRUE)\n'
        text += 'set(OPENSSL_VERSION "3.5.0")\nset(OPENSSL_VERSION_MAJOR 3)\n'
        text += 'set(OPENSSL_INCLUDE_DIR "${PREFIX_ROOT}/include")\n'
        modules['FindOpenSSL.cmake'] = text
        text = _imported('Brotli::common', PREFIX_LIBRARIES['Brotli::common'])
        text += _imported('Brotli::dec', PREFIX_LIBRARIES['Brotli::dec'], links=('Brotli::common',))
        text += 'set(BROTLI_FOUND TRUE)\nset(BROTLI_LIBRARIES Brotli::dec Brotli::common)\n'
        text += 'set(BROTLI_INCLUDE_DIRS "${PREFIX_ROOT}/include")\nset(BROTLI_LIBRARY_DIRS "${PREFIX_ROOT}/lib")\n'
        modules['FindBrotli.cmake'] = text
        text = _imported('FoundationNative::nghttp2', PREFIX_LIBRARIES['FoundationNative::nghttp2'],
                         definitions=('NGHTTP2_STATICLIB',))
        text += 'set(NGHTTP2_FOUND TRUE)\nset(NGHTTP2_LIBRARIES FoundationNative::nghttp2)\n'
        text += 'set(NGHTTP2_INCLUDE_DIRS "${PREFIX_ROOT}/include")\nset(NGHTTP2_LIBRARY_DIRS "${PREFIX_ROOT}/lib")\n'
        text += 'set(NGHTTP2_VERSION "1.64.0")\n'
        modules['FindNGHTTP2.cmake'] = text
        text = _imported('LibPSL::LibPSL', PREFIX_LIBRARIES['LibPSL::LibPSL'],
                         definitions=PSL_COMPILE_DEFINITIONS, links=PSL_SYSTEM_LINKS)
        text += 'set(LIBPSL_FOUND TRUE)\nset(Libpsl_FOUND TRUE)\nset(LIBPSL_LIBRARIES LibPSL::LibPSL)\n'
        text += 'set(LIBPSL_INCLUDE_DIRS "${PREFIX_ROOT}/include")\nset(LIBPSL_LIBRARY_DIRS "${PREFIX_ROOT}/lib")\n'
        modules['FindLibpsl.cmake'] = text
    return modules


def _project(context):
    supplier = context['supplier']
    text = '# Source-owned static Windows graph; no upstream configure entry.\n'
    text += 'cmake_minimum_required(VERSION 3.24)\n'
    for key, value in (('SOURCE_ROOT', context['source_root']),
                       ('PREFIX_ROOT', context['prefix_root']),
                       ('PROJECT_ROOT', context['project_root'])):
        text += 'set(' + key + ' ' + _literal(value) + ')\n'
    if supplier == 'xml2':
        text += 'set(FOUNDATION_XML2_HOST_ROOT ' + _literal(
            context['identity']['inventories']['host_generators']['root']) + ')\n'
    text += 'set(CMAKE_MODULE_PATH "${PROJECT_ROOT}/modules")\n'
    text += 'set(CMAKE_INSTALL_PREFIX "${PREFIX_ROOT}" CACHE PATH "Fixed prefix" FORCE)\n'
    text += 'set(CMAKE_INSTALL_INCLUDEDIR include CACHE PATH "Fixed public include directory" FORCE)\n'
    text += 'set(CMAKE_INSTALL_LIBDIR lib CACHE PATH "Fixed static archive directory" FORCE)\n'
    text += 'set(CMAKE_INSTALL_BINDIR bin CACHE PATH "Fixed binary directory" FORCE)\n'
    text += 'set(CMAKE_BUILD_TYPE Release CACHE STRING "Fixed configuration" FORCE)\n'
    text += 'set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded CACHE STRING "Static CRT" FORCE)\n'
    text += 'set(BUILD_SHARED_LIBS OFF CACHE BOOL "Static-only" FORCE)\n'
    for name, enabled in sorted(OPTIONS[supplier].items()):
        text += 'set(' + name + (' ON' if enabled else ' OFF') + ' CACHE BOOL "Fixed route" FORCE)\n'
    if supplier == 'curl':
        text += 'set(CURL_CA_PATH none CACHE STRING "No ambient CA directory" FORCE)\n'
        text += 'include("${PROJECT_ROOT}/configuration-1.cmake")\n'
        text += 'include("${PROJECT_ROOT}/configuration-2.cmake")\n'
        text += 'include("${PROJECT_ROOT}/library.cmake")\n'
    else:
        text += 'include("${PROJECT_ROOT}/project.cmake")\n'
    return text


def reviewed_supplier_commands(supplier, *, identity, source_layout, build_root,
                               prefix_root, source_recipe_bindings):
    if type(supplier) is not str or supplier not in OUTPUT_LIBRARIES:
        raise ValueError('One exact maintained four-supplier role required')
    context = _factory.factory_context(supplier, identity=identity,
        source_layout=source_layout, build_root=build_root, prefix_root=prefix_root,
        source_recipe_bindings=source_recipe_bindings)
    selected, headers = _selected_sources(context)
    modules = _dependency_modules(supplier)
    common = _factory.render_cmake_inputs(context)
    rendered = copy.deepcopy(common['rendered_files'])
    prefix = 'recipes/' + supplier + '/'
    rendered.append({'output': prefix + 'CMakeLists.txt', 'content': _project(context)})
    if supplier == 'curl':
        mapping = {'configuration-1.cmake': 'curl-configuration-1',
                   'configuration-2.cmake': 'curl-configuration-2',
                   'macros.cmake': 'curl-macros', 'library.cmake': 'curl-library'}
    else:
        mapping = {'project.cmake': supplier + '-project'}
    for output, name in mapping.items():
        rendered.append({'output': prefix + output, 'content': TEMPLATES[name]})
    for output, text in modules.items():
        rendered.append({'output': prefix + 'modules/' + output, 'content': text})
    rendered.sort(key=lambda row: row['output'])
    program = _factory.original_program(context, 'cmake')
    executable = program['declaration']['path']
    operations = [
        ('configure', [executable, '-S', context['project_root'], '-B', context['binary_root'],
                       '-G', 'Ninja', '-C', context['cache_file'],
                       '-DCMAKE_TOOLCHAIN_FILE:FILEPATH=' + context['toolchain_file'],
                       '-DCMAKE_BUILD_TYPE:STRING=Release']),
        ('build', [executable, '--build', context['binary_root'], '--config', 'Release', '--parallel', '4']),
        ('install', [executable, '--install', context['binary_root'], '--config', 'Release']),
    ]
    commands = []
    for stage, argv in operations:
        commands.append({'id': supplier + '-' + stage, 'supplier': supplier, 'stage': stage,
            'program': copy.deepcopy(program), 'argv': argv, 'cwd': context['workspace_root'],
            'environment': copy.deepcopy(context['environment']),
            'initial_cache': copy.deepcopy(common['references']['initial-cache.cmake']) if stage == 'configure' else None,
            'response_files': [], 'log_policy': 'stdout-stderr-combined'})
    result = {'commands': commands,
        'registration': {'stages': [{key: row[key] for key in ('id', 'supplier', 'stage')}
                                    for row in commands], 'produced_tools': {}},
        'source_files': selected, 'rendered_files': rendered, 'generated_inputs': [],
        'install_artifacts': {'libraries': copy.deepcopy(OUTPUT_LIBRARIES[supplier]), 'headers': headers}}
    return _factory.validate_factory_result(context, result)
