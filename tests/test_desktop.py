from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor,QImage
from PySide6.QtPdf import QPdfDocument

from idstudio.app import MainWindow,STYLE
from idstudio.core import DomainError
from idstudio.rendering import HEIGHT,WIDTH,export_pdf,image_bytes,normalize_signature,render_card
from idstudio.templates import default_templates
from idstudio.widgets import CropCanvas,TemplateDialog


def test_render_cr80_and_pdf_physical_dimensions(app,tmp_path):
    template=default_templates()["Corporate / Ocean"]
    front=render_card({"full_name":"Grace Namutebi","card_no":"STAFF-001"},template,"front")
    back=render_card({},template,"back")
    assert (front.width(),front.height())==(1011,638)
    assert QImage.fromData(image_bytes(front)).size()==front.size()
    path=tmp_path/"card.pdf"
    export_pdf(path,[front,back])
    pdf=QPdfDocument()
    assert pdf.load(str(path))==QPdfDocument.Error.None_
    assert pdf.pageCount()==2
    size=pdf.pagePointSize(0)
    assert abs(size.width()*25.4/72-85.60)<.4
    assert abs(size.height()*25.4/72-53.98)<.4


def test_white_signature_rejected(app):
    image=QImage(200,100,QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    with pytest.raises(DomainError,match="no visible ink"):
        normalize_signature(image)


def test_signature_background_becomes_transparent(app):
    image=QImage(200,100,QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    image.setPixelColor(50,50,QColor("black"))
    result=normalize_signature(image)
    assert result.pixelColor(0,0).alpha()==0
    assert result.pixelColor(50,50).alpha()>0


def test_crop_keeps_portrait_filled(app):
    image=QImage(800,600,QImage.Format.Format_RGB32)
    image.fill(QColor("#c0ffee"))
    canvas=CropCanvas(image)
    canvas.set_zoom(200)
    canvas.offset.setX(900)
    canvas.offset.setY(-9999)
    canvas.clamp()
    result=canvas.result()
    assert result.size().width()==660
    assert result.pixelColor(0,0).name()=="#c0ffee"
    assert result.pixelColor(659,869).name()=="#c0ffee"


def test_window_enrollment_and_navigation(app,store,values,tmp_path):
    app.setStyleSheet(STYLE)
    window=MainWindow(store)
    window.show()
    app.processEvents()
    window.new_record()
    for key in window.inputs:
        window.inputs[key].setText(values[key])
    photo=QImage(660,870,QImage.Format.Format_RGB32)
    photo.fill(QColor("#c6dce5"))
    window.photo=image_bytes(photo)
    window.signature=image_bytes(photo)
    window.consent.setChecked(True)
    window.save_record()
    assert window.current_record["card_no"]=="EMP-001"
    assert not window.dirty
    for i in range(6):
        window.navigate(i)
        app.processEvents()
        assert window.pages.currentIndex()==i
    window.navigate(2)
    window.refresh_preview()
    app.processEvents()
    assert not window.card_preview.original.isNull()
    window.grab().save(str(tmp_path/"enrollment.png"))
    window.idle_timer.stop()
    window.close()


def test_template_editor_round_trip(app,store):
    name="Corporate / Ocean"
    dialog=TemplateDialog(store,name,store.templates()[name])
    dialog.read_table()
    assert dialog.template==store.templates()[name]
    dialog.side.setCurrentText("back")
    assert dialog.current_side=="back"
    assert dialog.table.rowCount()==len(dialog.template["back"])
    dialog.close()
