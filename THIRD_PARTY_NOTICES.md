# Third-party software

MineColorTrack is Copyright (C) 2026 EQQX2 and licensed under the GNU General Public License,
version 3 or (at your option) any later version. See `LICENSE`. Source code:
https://github.com/EQQX0/MineColorTrack

The Windows installer bundles the following components. Each keeps its own licence; the full texts are
included with the packages they come from (inside the installed `_internal` folder) and on their project pages.

| Component | Use in MineColorTrack | Licence |
|---|---|---|
| Python | runtime | Python Software Foundation License |
| PyQt6 (Riverbank Computing) | user interface | GPL-3.0-only |
| Qt 6 (The Qt Company), via PyQt6-Qt6 | user interface | LGPL-3.0 |
| PyQt6-sip | Python/Qt bridge | BSD-2-Clause |
| OpenCV, via opencv-python-headless | image processing | Apache-2.0 (bundled parts list their own licences in LICENSE-3RD-PARTY.txt) |
| NumPy | arrays | BSD-3-Clause (with 0BSD, MIT, Zlib and CC0-1.0 parts) |
| mss | compatible screen capture | MIT |
| dxcam | fast screen capture (Windows Desktop Duplication) | MIT |
| comtypes | Windows COM access for dxcam | MIT |
| ONNX Runtime (onnxruntime-directml, Microsoft) | running AI models | MIT; the included DirectML library is under Microsoft's redistributable licence (see the package's ThirdPartyNotices) |
| Inno Setup (Jordan Russell, Martijn Laan) | builds the installer (not part of the app) | Inno Setup License |

Not bundled: the Google Colab training notebook installs and uses **Ultralytics YOLO** (AGPL-3.0) inside
Colab. Ultralytics considers models trained with it to fall under AGPL-3.0 as well; MineColorTrack itself does
not include Ultralytics code.

Public datasets you may import (for example from Roboflow Universe or Hugging Face) have their own licences,
often CC BY 4.0, which require crediting the author.
