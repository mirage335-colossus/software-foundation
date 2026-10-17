# Source-only proposal. Do not run without separately authorized native admission.
# Fixed argv: selected perl.exe -T -f -- <this pinned script>; no arguments.
die "unexpected emitter arguments\n" if @ARGV;
binmode(STDOUT) or die "cannot set binary stdout\n";
my $release = sprintf('%vd', $^V);
die "non-numeric Perl version builtin\n"
    unless $release =~ /\A(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\z/;
my $taint = ${^TAINT};
die "enforced taint mode unavailable\n" unless $taint == 1;
printf STDOUT
    "{\"schema_version\":1,\"kind\":\"foundation-native-engine-runtime-version-v1\",\"role\":\"perl\",\"perl_version\":\"%s\",\"taint_mode\":%d}\n",
    $release, $taint
    or die "cannot write builtin observation\n";
close(STDOUT) or die "cannot close builtin observation\n";
exit 0;

