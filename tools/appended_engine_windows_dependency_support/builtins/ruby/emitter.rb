# coding: US-ASCII
# Source-only candidate. Do not execute without the separately authorized runner.
# No require, caller-supplied version, status, or source text is accepted.

raise ArgumentError, 'runtime version emitter accepts no arguments' unless ARGV.empty?

def json_ascii_string(value)
  raise TypeError, 'runtime version fact must be a String' unless value.instance_of?(String)

  result = '"'
  value.each_byte do |byte|
    unless byte >= 32 && byte <= 126
      raise ArgumentError, 'runtime version fact must contain printable ASCII only'
    end
    result << '\\' if byte == 34 || byte == 92
    result << byte
  end
  result << '"'
end

unless RUBY_PATCHLEVEL.instance_of?(Integer)
  raise TypeError, 'runtime patch level must be an Integer'
end

output = '{"schema_version":1,"kind":"foundation-native-engine-runtime-version-v1","role":"ruby","ruby_version":'
output << json_ascii_string(RUBY_VERSION)
output << ',"ruby_engine":' << json_ascii_string(RUBY_ENGINE)
output << ',"ruby_engine_version":' << json_ascii_string(RUBY_ENGINE_VERSION)
output << ',"ruby_patchlevel":' << RUBY_PATCHLEVEL.to_s << "}\n"

STDOUT.binmode
written = STDOUT.write(output)
raise IOError, 'runtime version output was not completely written' unless written == output.bytesize
STDOUT.close
