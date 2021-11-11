
I want to support binary operator `=`. Several problems arise:

# Inline vs Multiline.

Indent-oriented parsing works.
Could implement full-blown binop expression parser inline.
Would need separate rules for trailing `=` that indicated multiline value.

# Spacing significance.
`a=b c` looks different from `a = b c`.



```
a = 1 2 3
b=1 2 3


a = 1
b =
 2
 3
 4


```