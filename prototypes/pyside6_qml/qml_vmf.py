from __future__ import annotations

import enum
import math
import struct
from typing import List

from PySide6.QtCore import Property, QByteArray, QObject, Signal, Slot
from PySide6.QtGui import QVector3D
from PySide6.QtQuick3D import QQuick3DGeometry
from PySide6.QtQml import QmlElement
import vmf_tool


# QmlElement decorator globals
QML_IMPORT_NAME = "Vmf"
QML_IMPORT_MAJOR_VERSION = 1
QML_IMPORT_MINOR_VERSION = 0


def fan_indices(start: int, length: int) -> List[int]:
    """converts line loop indices to triangle fan"""
    if length < 3:
        raise RuntimeError(f"Invalid face! Only {length} vertices!")
    out = [start, start + 1, start + 2]
    for i in range(length - 3):
        out.extend((start, out[-1], start + 3 + i))
    return out


@QmlElement
class BrushGeometry(QQuick3DGeometry):
    """should be created dynamically"""
    _brush: vmf_tool.solid.Brush

    def __init__(self, brush: vmf_tool.solid.Brush):
        super().__init__()
        self._brush = brush
        self.rebuildGeometry()

    # TODO: signals & slots for editing geo etc.

    def rebuildGeometry(self):
        i = 0
        indices = list()
        vertices = list()
        mins = [math.inf] * 3
        maxs = [-math.inf] * 3
        for face in self._brush.faces:
            indices.extend(fan_indices(i, len(face.polygon)))
            for vertex in face.polygon:
                mins = [min(a, b) for a, b in zip(mins, vertex)]
                maxs = [max(a, b) for a, b in zip(maxs, vertex)]
                vertices.extend((*vertex, *face.plane[0], face.uaxis.linear_pos(vertex), face.vaxis.linear_pos(vertex)))
            i += len(face.polygon)
        self.setBounds(QVector3D(*mins), QVector3D(*maxs))  # needed for raycast picking
        # vertex data
        vertex_bytes = QByteArray(struct.iter_pack("8f", vertices))
        self.setVertices(vertex_bytes)
        self.addAttribute(QQuick3DGeometry.Attribute.PositionSemantic, 0, QQuick3DGeometry.ComponentType.F32Type)
        self.addAttribute(QQuick3DGeometry.Attribute.NormalSemantic, 3 * 4, QQuick3DGeometry.ComponentType.F32Type)
        self.addAttribute(QQuick3DGeometry.Attribute.TexCoord0Semantic, 6 * 4, QQuick3DGeometry.ComponentType.F32Type)
        self.setStride(8 * 4)
        # index data
        index_bytes = QByteArray(struct.iter_pack("H", indices))
        self.addAttribute(QQuick3DGeometry.Attribute.IndexSemantic, 0, QQuick3DGeometry.ComponentType.U16Type)
        self.setIndices(index_bytes)


@QmlElement
class VmfInterface(QObject):
    _vmf: vmf_tool.Vmf
    _status: str  # status Property
    filename: str  # source Property
    sourceChanged = Signal(str)
    statusChanged = Signal(str)

    def __init__(self, parent=None, filename: str = ""):
        super().__init__(parent)
        self.filename = filename
        self._vmf = vmf_tool.Vmf(filename)
        self._status = "Unloaded"
        # internal Signal & Slot connections
        self.sourceChanged.connect(self.loadVmf)  # setting self.source reads the .vmf file at that location

    def brushCount(self):
        return len(self._vmf.brushes)

    def brushGeometryAt(self, index: int) -> BrushGeometry:
        brushes = list(self._vmf.brushes.values())
        # TODO: link created Geo to brush to pass changes back
        return BrushGeometry(brushes[index])

    def brushColourAt(self, index: int) -> str:
        brushes = list(self._vmf.brushes.values())
        return "#" + "".join([f"{int(255*x):02X}" for x in brushes[index].colour])

    @Slot(str)
    def loadVmf(self, filename: str):
        # TODO: let a QRunnable & QThreadPool handle this
        try:
            self.status = "Loading"
            print(f"Loading {filename}...")
            self._vmf = vmf_tool.Vmf.from_file(filename)
            print(f"Loaded {filename}!")
            self.status = "Loaded"
        except Exception:
            # TODO: store some text detailing the error as a property
            self.status = "Error"

    @Property(str)
    def source(self) -> str:
        return self.filename

    @source.setter
    def source(self, new_filename: str):
        if new_filename.startswith("file://"):
            new_filename = new_filename[len("file://"):]
        if new_filename == self.filename:
            return
        self.filename = new_filename
        self.sourceChanged.emit(new_filename)

    @Property(str)
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, new_status: str):
        if new_status == self._status:
            return
        self._status = new_status
        self.statusChanged.emit(new_status)
