// The shared artifact is inspected but never loaded or executed by this recipe.
extern "C" int foundation_native_dependency_pic_probe()
{
    return 1;
}
