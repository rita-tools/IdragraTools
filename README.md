# IdragraTools

IdrAgraTools is a QGIS plugin designed to assist input preparation and output visualization for the [IdrAgra model](https://github.com/rita-tools/IdrAgra).

IdrAgraTools is developed and tested on Windows with QGIS 3.34.3 and 3.44.15. macOS support is tentative.

## Installation

1. Download the `IdragraTools` ZIP from the [releases](https://github.com/rita-tools/IdrAgraTools/releases) page (**not** from `Source code (zip)`).
2. In QGIS, open **Plugins → Manage and Install Plugins → Install from ZIP**.
3. Select the downloaded ZIP and click **Install Plugin**.
4. If necessary, enable **Idragra Tools** in the **Installed** tab.

## Producing an installable zip

Installation zips are available on the [releases](https://github.com/rita-tools/IdrAgraTools/releases) page.
Alternatively, advanced users can re-create a new zip from the latest github commit using: clone the repository, apply edits to the source code and, when satisfied, produce a new zip using: `git archive --format=zip --prefix=IdragraTools/ --output=IdragraTools.zip HEAD`. Note that manually zipping the repository's root produces a similar result.