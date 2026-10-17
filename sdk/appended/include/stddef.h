#ifndef FOUNDATION_GUEST_STDDEF_H
#define FOUNDATION_GUEST_STDDEF_H
typedef __SIZE_TYPE__ size_t;
typedef __PTRDIFF_TYPE__ ptrdiff_t;
#if defined(__cplusplus)
#define NULL 0
#else
#define NULL ((void *)0)
#endif
#define offsetof(type, member) __builtin_offsetof(type, member)
#endif
