include_guard(GLOBAL)

# Closed missing-recipe catalogue only. No supplier command, artifact path,
# imported target, source projection or generated build graph is admitted here.
set(FOUNDATION_WINDOWS_DEPENDENCY_EXECUTABLE_PLAN FALSE)
set(FOUNDATION_WINDOWS_DEPENDENCY_BUILD FALSE)
set(FOUNDATION_WINDOWS_DEPENDENCY_MISSING_INPUTS
  "windows-supplier-recipe-icu: source-review.json#/sources/icu (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-zlib: source-review.json#/sources/zlib (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-brotli: source-review.json#/sources/brotli (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-png: source-review.json#/sources/png (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-jpeg: source-review.json#/sources/jpeg (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-webp: source-review.json#/sources/webp (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-harfbuzz: source-review.json#/sources/harfbuzz (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-xml2: source-review.json#/sources/xml2 (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-sqlite: source-review.json#/sources/sqlite (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-openssl: source-review.json#/sources/openssl (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-nghttp2: source-review.json#/sources/nghttp2 (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-psl: source-review.json#/sources/psl (Windows entrypoint review unperformed)"
  "windows-supplier-recipe-curl: source-review.json#/sources/curl (Windows entrypoint review unperformed)"
)
