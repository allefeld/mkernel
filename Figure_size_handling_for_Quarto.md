# Figure size handling for Quarto

When processing a document, Quarto provides [document-level options](https://quarto.org/docs/advanced/jupyter/kernel-execution.html#quarto-document-options) to the kernel, including

`fig-width`: the requested figure width in inches

`fig-height`: the requested figure height in inches

Matlab's synchronization of `PaperPosition` and `Position` poses a problem for reliable implementation of these Quarto options. They should seamlessly work if the user doesn't manipulate defaults explicitly, but not interfere with normal operation and therefore avoid changing defaults as far as possible.

If `PaperPositionMode` is `'auto'`, it is impossible to set the `PaperPosition` of new figures via `defaultFigurePaperPosition`, because even if `defaultFigurePosition` is not set, there is always the fallback `factoryFigurePosition` which overrides it.

We choose the following strategy which limits interference to `Paper*` properties.

-   set `defaultFigurePaperUnits` to `inches`
-   set `defaultFigurePaperPosition` to `[0, 0, fig-width, fig-height]`
-   set `defaultFigurePaperPositionMode` to `'manual'`
