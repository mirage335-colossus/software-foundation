// Uncompiled Windows probe source. No supplier API or closure is assumed here.
// A future reviewed link must retain all twenty selected static archives with
// explicit /WHOLEARCHIVE inputs and inspect the actual linked result. Merely
// compiling or calling this function supplies no dependency-link evidence.
extern "C" __declspec(dllexport) unsigned int
foundation_native_dependency_link_probe() noexcept
{
    return 0x46574431U; // FWD1: probe ABI tag, not a qualification result.
}

int main()
{
    return foundation_native_dependency_link_probe() == 0x46574431U ? 0 : 1;
}
