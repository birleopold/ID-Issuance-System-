from __future__ import annotations

import base64
import copy
import json
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSlider, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .core import DomainError
from .rendering import image_bytes, load_image, normalize_signature, render_card, validate_assets
from .templates import FIELDS


def button(label, callback, primary=False):
    control = QPushButton(label)
    control.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        control.setProperty("primary", True)
    control.clicked.connect(callback)
    return control


def show_error(parent, exc):
    QMessageBox.warning(parent, "Action needs attention", str(exc))


class ImagePreview(QLabel):
    def __init__(self, height=260):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(200, height)
        self.setStyleSheet("background: #e9eef4; border: 1px solid #d9e2ec; border-radius: 10px;")
        self.original = QPixmap()

    def set_image(self, image):
        self.original = QPixmap.fromImage(image)
        self.refresh()

    def refresh(self):
        if not self.original.isNull():
            self.setPixmap(self.original.scaled(max(1,self.width()-24), max(1,self.height()-24), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.refresh()


class CropCanvas(QWidget):
    def __init__(self, image):
        super().__init__()
        self.source = image
        self.setFixedSize(330, 435)
        self.factor = max(330/image.width(), 435/image.height())
        self.zoom = 1
        self.offset = QPointF((330-image.width()*self.factor)/2, (435-image.height()*self.factor)/2)
        self.last = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def clamp(self):
        scale = self.factor*self.zoom
        self.offset.setX(min(0, max(330-self.source.width()*scale, self.offset.x())))
        self.offset.setY(min(0, max(435-self.source.height()*scale, self.offset.y())))

    def set_zoom(self, value):
        previous = self.factor*self.zoom
        self.zoom = value/100
        current = self.factor*self.zoom
        self.offset = QPointF(165-(165-self.offset.x())*current/previous, 217.5-(217.5-self.offset.y())*current/previous)
        self.clamp()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        s = self.factor*self.zoom
        painter.drawImage(QRectF(self.offset.x(), self.offset.y(), self.source.width()*s, self.source.height()*s), self.source)
        painter.setPen(QPen(QColor(255,255,255,130), 1))
        for x in (110,220):
            painter.drawLine(x,0,x,435)
        for y in (145,290):
            painter.drawLine(0,y,330,y)

    def mousePressEvent(self, event):
        self.last = event.position()

    def mouseMoveEvent(self, event):
        if self.last is not None:
            self.offset += event.position()-self.last
            self.last = event.position()
            self.clamp()
            self.update()

    def mouseReleaseEvent(self, event):
        self.last = None

    def result(self):
        out = QImage(660,870,QImage.Format.Format_RGB32)
        out.fill(Qt.GlobalColor.white)
        painter = QPainter(out)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        s = self.factor*self.zoom*2
        painter.drawImage(QRectF(self.offset.x()*2,self.offset.y()*2,self.source.width()*s,self.source.height()*s),self.source)
        painter.end()
        return out


class CropDialog(QDialog):
    def __init__(self, image, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Frame the portrait")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Drag to position the face. Use the slider to zoom."))
        self.canvas = CropCanvas(image)
        layout.addWidget(self.canvas, alignment=Qt.AlignmentFlag.AlignCenter)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(100,300)
        slider.setValue(100)
        slider.valueChanged.connect(self.canvas.set_zoom)
        layout.addWidget(slider)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class InkCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(720,240)
        self.image = QImage(1440,480,QImage.Format.Format_ARGB32)
        self.clear()
        self.last = None

    def clear(self):
        self.image.fill(Qt.GlobalColor.transparent)
        self.has_ink = False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("white"))
        painter.drawImage(self.rect(),self.image)
        painter.setPen(QPen(QColor("#cbd5e1"),1,Qt.PenStyle.DashLine))
        painter.drawLine(25,190,695,190)

    def mousePressEvent(self,event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last = event.position()*2

    def mouseMoveEvent(self,event):
        if self.last is not None:
            point = event.position()*2
            painter = QPainter(self.image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor("#142332"),4,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(self.last,point)
            painter.end()
            self.last = point
            self.has_ink = True
            self.update()

    def mouseReleaseEvent(self,event):
        self.last = None


class SignatureDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle("Capture signature")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Sign using a mouse, touch screen or pen. This captures an image of the signature."))
        self.canvas = InkCanvas()
        layout.addWidget(self.canvas)
        row = QHBoxLayout()
        row.addWidget(button("Clear",self.canvas.clear))
        row.addStretch()
        row.addWidget(button("Cancel",self.reject))
        row.addWidget(button("Use signature",self.save,True))
        layout.addLayout(row)

    def save(self):
        if not self.canvas.has_ink:
            show_error(self,"Please draw a signature first.")
            return
        self.accept()


class CameraDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        from PySide6.QtMultimedia import QCamera, QImageCapture, QMediaCaptureSession, QMediaDevices
        from PySide6.QtMultimediaWidgets import QVideoWidget
        self.setWindowTitle("Camera · portrait capture")
        self.resize(800,620)
        self.image = None
        self.camera = None
        layout = QVBoxLayout(self)
        self.devices = QMediaDevices.videoInputs()
        self.selector = QComboBox()
        for device in self.devices:
            self.selector.addItem(device.description())
        layout.addWidget(self.selector)
        self.video = QVideoWidget()
        layout.addWidget(self.video,1)
        self.status = QLabel("Connect a camera, or use Import photo.")
        layout.addWidget(self.status)
        self.session = QMediaCaptureSession()
        self.session.setVideoOutput(self.video)
        self.capture = QImageCapture()
        self.session.setImageCapture(self.capture)
        self.capture.imageCaptured.connect(self.captured)
        self.capture.errorOccurred.connect(lambda *args:self.status.setText("Camera capture failed. Check permissions and reconnect the device."))
        self.take = button("Take photo",self.take_photo,True)
        self.take.setEnabled(False)
        self.capture.readyForCaptureChanged.connect(self.take.setEnabled)
        layout.addWidget(self.take)
        self.selector.currentIndexChanged.connect(self.select_camera)
        if self.devices:
            self.select_camera(0)

    def select_camera(self,index):
        from PySide6.QtMultimedia import QCamera
        if self.camera:
            self.camera.stop()
        self.camera = QCamera(self.devices[index])
        self.camera.errorOccurred.connect(lambda *args:self.status.setText("Camera unavailable. Check Windows camera permissions and close other camera apps."))
        self.session.setCamera(self.camera)
        self.camera.start()
        self.status.setText("Look toward the camera. Keep the face evenly lit.")

    def take_photo(self):
        self.capture.capture()

    def captured(self,request_id,image):
        self.image = image.copy()
        self.accept()

    def done(self,result):
        if self.camera:
            self.camera.stop()
        super().done(result)


class TemplateDialog(QDialog):
    """Visual preview with millimeter field controls, portable JSON import/export."""
    def __init__(self,store,name,template,parent=None):
        super().__init__(parent)
        self.store = store
        self.template = copy.deepcopy(template)
        self.setWindowTitle("Template studio · CR80")
        self.resize(1180,760)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(name)
        self.org = QLineEdit(template["organization"])
        self.accent = QLineEdit(template["accent"])
        form.addRow("Template name / revision",self.name)
        form.addRow("Organization",self.org)
        form.addRow("Accent color",self.accent)
        layout.addLayout(form)
        row = QHBoxLayout()
        self.side = QComboBox()
        self.side.addItems(["front","back"])
        row.addWidget(self.side)
        row.addWidget(button("Import background",self.background))
        row.addWidget(button("Remove background",self.remove_background))
        row.addWidget(button("Import template",self.import_template))
        row.addWidget(button("Export template",self.export_template))
        layout.addLayout(row)
        content = QHBoxLayout()
        self.table = QTableWidget(0,9)
        self.table.setHorizontalHeaderLabels(["Field","X mm","Y mm","W mm","H mm","Size pt","Color","Static text"," "])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        content.addWidget(self.table,3)
        self.preview = ImagePreview(280)
        content.addWidget(self.preview,2)
        layout.addLayout(content,1)
        self.feedback = QLabel("Keep critical content away from the card edge. Save revisions under a new name.")
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        actions = QHBoxLayout()
        actions.addWidget(button("Add text field",self.add_field))
        actions.addStretch()
        actions.addWidget(button("Cancel",self.reject))
        actions.addWidget(button("Save template",self.save,True))
        layout.addLayout(actions)
        self.current_side = "front"
        self.side.currentTextChanged.connect(self.switch_side)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.refresh)
        self.table.cellChanged.connect(lambda *_:self.timer.start())
        self.org.textChanged.connect(lambda *_:self.timer.start())
        self.accent.textChanged.connect(lambda *_:self.timer.start())
        self.fill_table()
        self.refresh()

    def fill_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for item in self.template[self.current_side]:
            row = self.table.rowCount()
            self.table.insertRow(row)
            kind = QComboBox()
            kind.addItems(FIELDS)
            kind.setCurrentText(item["key"])
            kind.currentTextChanged.connect(lambda *_:self.timer.start())
            self.table.setCellWidget(row,0,kind)
            for column,key in enumerate(("x","y","w","h","size","color","text"),1):
                self.table.setItem(row,column,QTableWidgetItem(str(item.get(key,""))))
            self.table.setCellWidget(row,8,button("×",lambda checked=False,r=row:self.delete_field(r)))
        self.table.blockSignals(False)

    def read_table(self):
        items=[]
        for row in range(self.table.rowCount()):
            item={"key":self.table.cellWidget(row,0).currentText()}
            for column,key in enumerate(("x","y","w","h","size","color","text"),1):
                value=self.table.item(row,column).text()
                item[key]=float(value) if column<=5 else value
            items.append(item)
        self.template[self.current_side]=items
        self.template["organization"]=self.org.text().strip()
        self.template["accent"]=self.accent.text().strip()

    def refresh(self):
        try:
            self.read_table()
            sample={"full_name":"Alex Morgan","title":"Operations Manager","department":"People & Operations","card_no":"STAFF-001","expires":"2028-12-31"}
            self.preview.set_image(render_card(sample,self.template,self.current_side))
            self.feedback.setText("Preview ready · positions are measured in millimeters · 85.60 × 53.98 mm")
        except (ValueError,DomainError) as exc:
            self.feedback.setText("Check template: " + str(exc))

    def switch_side(self,side):
        try:
            self.read_table()
        except ValueError:
            self.side.blockSignals(True)
            self.side.setCurrentText(self.current_side)
            self.side.blockSignals(False)
            show_error(self,"Fix invalid numeric values before changing sides.")
            return
        self.current_side=side
        self.fill_table()
        self.refresh()

    def delete_field(self,row):
        try:
            self.read_table()
            self.template[self.current_side].pop(row)
            self.fill_table()
            self.refresh()
        except ValueError as exc:
            show_error(self,exc)

    def add_field(self):
        from .templates import field
        try:
            self.read_table()
            self.template[self.current_side].append(field("text",5,20,40,6,text="New label"))
            self.fill_table()
            self.refresh()
        except ValueError as exc:
            show_error(self,exc)

    def background(self):
        path,_=QFileDialog.getOpenFileName(self,"Select background","","Images (*.png *.jpg *.jpeg)")
        if path:
            try:
                image=load_image(path).scaled(2022,1275,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
                self.template[self.current_side+"_background"]=base64.b64encode(image_bytes(image)).decode()
                self.refresh()
            except Exception as exc:
                show_error(self,exc)

    def remove_background(self):
        self.template[self.current_side+"_background"]=""
        self.refresh()

    def import_template(self):
        path,_=QFileDialog.getOpenFileName(self,"Import template","","Template (*.json)")
        if path:
            try:
                if Path(path).stat().st_size>25_000_000:
                    raise DomainError("Template file is too large.")
                value=json.loads(Path(path).read_text(encoding="utf-8"))
                validate_assets(value)
                self.template=value
                self.org.setText(value["organization"])
                self.accent.setText(value["accent"])
                self.name.setText(Path(path).stem)
                self.fill_table()
                self.refresh()
            except Exception as exc:
                show_error(self,exc)

    def export_template(self):
        try:
            self.read_table()
            validate_assets(self.template)
            path,_=QFileDialog.getSaveFileName(self,"Export portable template","card-template.json","Template (*.json)")
            if path:
                Path(path).write_text(json.dumps(self.template,indent=2),encoding="utf-8")
        except Exception as exc:
            show_error(self,exc)

    def save(self):
        try:
            self.read_table()
            validate_assets(self.template)
            self.store.save_template(self.name.text(),self.template)
            self.accept()
        except Exception as exc:
            show_error(self,exc)
