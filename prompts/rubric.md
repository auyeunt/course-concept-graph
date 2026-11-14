## Strength rubric

Strength measures how much the development of Y in this module's text depends
on X: how badly a student who lacks X would be stuck when reading about Y. It is
a number from 0 to 1. Use the anchors, and interpolate (0.7, 0.35) when an edge
falls between them.

- 1.0  definitional: Y is defined in terms of X; Y cannot even be stated without X.
- 0.8  core: the central argument, mechanism or explanation of Y rests on X.
- 0.6  substantial: X carries a real step in developing Y (a derivation step, or
       the worked example through which Y is actually taught).
- 0.4  secondary: X is used, but Y could be taught without it after a little
       rewording (an alternative route, a second justification).
- 0.2  supporting: X appears only as notation, a check or verification, an
       implementation side-argument, an illustration or an analogy.
- 0.0  no support: the text does not use X in developing Y, or uses Y to explain
       X (the reverse direction).

Example, from a module that develops a "carry" function for addition: the
positional-value idea that the next column is worth b times this one is why a
carry exists at all (0.8); writing carry as a C function is notation (0.2);
tabulating it to show it equals logical AND is a check (0.2); arguing it can be
built from NAND gates is an implementation side-argument (0.2).

Judge each edge by the passage that develops Y, not by how important X is in
general. Grade the edges already in the graph as strictly as the new ones: they
were written by an earlier reader whose threshold was never recorded.
