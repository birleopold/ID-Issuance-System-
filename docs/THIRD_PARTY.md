# Distribution notes

The application uses PySide6/Qt, Python, pywin32 and the PyInstaller bootloader, each under its own licence. The build copies installed distribution metadata and available licence/notice files into `THIRD_PARTY_NOTICES` next to the executable. In addition, retain notices and licences contained in the packaged Qt runtime.

This project uses PySide6 rather than PyQt6. Packaging is deliberately onedir, with Qt DLLs outside the Python archive. Before commercial distribution, review the actual Qt modules and multimedia/codec components shipped by the selected wheels, applicable LGPL/GPL/commercial choices, notices, source/relinking obligations and the customer agreement. Do not assume collecting notice files alone satisfies every obligation. Decide whether a commercial Qt licence is appropriate for the final product/distribution model.

Wacom's SDK and hardware drivers are proprietary external prerequisites. They are not copied into this repository or installer. The deployment owner must obtain licensing and any redistribution rights from the vendor. Printer drivers are supplied by their respective manufacturers.

No application licence has been imposed on the repository owner by this implementation. Choose the product’s commercial terms and support policy before distributing to customers.
