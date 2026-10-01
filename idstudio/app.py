from __future__ import annotations

import argparse
import csv
import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import time

from PySide6.QtCore import QDate, QEvent, QLockFile, QTimer, Qt
from PySide6.QtGui import QImage, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
    QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QScrollArea, QSplitter, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

from . import __version__
from .core import DomainError, Store, data_directory
from .devices import capture_wacom, configured_printer, printer_names, submit_print
from .rendering import export_pdf, image_bytes, load_image, normalize_signature, render_card
from .templates import default_templates
from .widgets import CSVImportDialog, CameraDialog, CropDialog, ImagePreview, SignatureDialog, TemplateDialog, button, show_error
from .fileio import atomic_output

STYLE = """
* { font-family: 'Segoe UI', 'DejaVu Sans'; font-size: 13px; }
QMainWindow, QDialog { background: #f4f7fb; }
QLabel { color: #23364d; }
QLabel[heading=true] { font-size: 26px; font-weight: 700; color: #10283f; }
QLabel[muted=true] { color: #63768c; }
QWidget#sidebar { background: #10283f; }
QWidget#sidebar QLabel { color: #dce7f2; }
QWidget#sidebar QPushButton { background: transparent; color: #c6d5e4; border: none; text-align: left; padding: 13px; }
QWidget#sidebar QPushButton:checked { background: #1c435c; color: white; border-left: 3px solid #43d3c3; }
QWidget#sidebar QPushButton:hover { background: #1c435c; }
QPushButton { background: white; color: #23364d; padding: 9px 14px; border: 1px solid #cbd7e4; border-radius: 6px; font-weight: 600; }
QPushButton:hover { background: #e9f1f7; border-color: #7298b3; }
QPushButton[primary=true] { background: #087e83; border-color: #087e83; color: white; }
QPushButton[primary=true]:hover { background: #06696e; }
QPushButton:disabled { background: #e8edf2; color: #8b99a8; border-color: #d9e2ec; }
QLineEdit, QComboBox, QDateEdit { background: white; color: #1e354d; padding: 9px; border: 1px solid #cbd7e4; border-radius: 5px; min-height: 18px; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus { border: 2px solid #168b95; }
QTableWidget { background: white; color: #243b53; border: 1px solid #dce4ee; gridline-color: #edf1f6; selection-background-color: #d9eeef; selection-color: #10283f; }
QHeaderView::section { background: #edf2f7; color: #52677b; padding: 11px; border: none; font-weight: 600; }
QTableWidget::item { padding: 8px; }
QFrame[panel=true] { background: white; border: 1px solid #dce4ee; border-radius: 10px; }
QCheckBox { color: #334b64; spacing: 9px; }
QScrollArea { border: none; background: transparent; }
QStatusBar { color: #52677b; background: #eaf0f6; }
"""


def title(text, muted=False):
    label=QLabel(text)
    label.setProperty("muted" if muted else "heading",True)
    label.setWordWrap(True)
    return label


def table(headers):
    view=QTableWidget(0,len(headers))
    view.setHorizontalHeaderLabels(headers)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    view.verticalHeader().setVisible(False)
    view.verticalHeader().setDefaultSectionSize(44)
    view.setAlternatingRowColors(True)
    return view


def populate(view,rows,keys):
    view.setRowCount(len(rows))
    for i,row in enumerate(rows):
        for j,key in enumerate(keys):
            cell=QTableWidgetItem(str(row[key]))
            cell.setData(Qt.ItemDataRole.UserRole,row["id"] if "id" in row.keys() else None)
            view.setItem(i,j,cell)


class LoginDialog(QDialog):
    def __init__(self,store,parent=None):
        super().__init__(parent)
        self.store=store
        self.setup=not store.has_users()
        self.setWindowTitle("Credential Studio · " + ("Welcome" if self.setup else "Sign in"))
        self.setFixedWidth(460)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(32,32,32,32)
        layout.setSpacing(18)
        layout.addWidget(title("Set up your workstation" if self.setup else "Welcome back"))
        layout.addWidget(title("Create the first administrator account." if self.setup else "Sign in to your local issuance workspace.",True))
        self.username=QLineEdit()
        self.username.setPlaceholderText("Username")
        self.password=QLineEdit()
        self.password.setPlaceholderText("Password · at least 12 characters" if self.setup else "Password")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm=QLineEdit()
        self.confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm.setPlaceholderText("Confirm password")
        layout.addWidget(self.username)
        layout.addWidget(self.password)
        if self.setup:
            layout.addWidget(self.confirm)
        self.error=QLabel("")
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #b93846")
        layout.addWidget(self.error)
        layout.addWidget(button("Create administrator" if self.setup else "Sign in",self.sign_in,True))
        self.password.returnPressed.connect(self.sign_in)
        self.confirm.returnPressed.connect(self.sign_in)

    def sign_in(self):
        try:
            if self.setup:
                if self.password.text()!=self.confirm.text():
                    raise DomainError("Passwords do not match.")
                self.store.create_user(self.username.text(),self.password.text(),"admin")
                self.setup=False
            self.store.login(self.username.text(),self.password.text())
            self.accept()
        except DomainError as exc:
            self.error.setText(str(exc))


class MainWindow(QMainWindow):
    def __init__(self,store):
        super().__init__()
        self.store=store
        self.setWindowTitle("Credential Studio · Identity issuance")
        self.resize(1440,900)
        self.setMinimumSize(1120,740)
        self.current_record=None
        self.photo=None
        self.signature=None
        self.dirty=False
        self.loading=False
        self.last_activity=time.monotonic()
        self.locking=False
        root=QWidget()
        self.setCentralWidget(root)
        shell=QHBoxLayout(root)
        shell.setContentsMargins(0,0,0,0)
        shell.setSpacing(0)
        sidebar=QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        nav=QVBoxLayout(sidebar)
        nav.setContentsMargins(18,26,18,20)
        logo=QLabel("CREDENTIAL\nSTUDIO")
        logo.setStyleSheet("font-size: 23px; font-weight: 800; letter-spacing: 2px;")
        nav.addWidget(logo)
        sub=QLabel("ISSUANCE WORKSPACE")
        sub.setStyleSheet("font-size: 10px; color: #6caab9; margin-bottom: 25px;")
        nav.addWidget(sub)
        self.nav_buttons=[]
        for index,label in enumerate(["Overview","Cardholders","Enrollment","Template studio","Print history","Administration"]):
            control=button(label,lambda checked=False,i=index:self.navigate(i))
            control.setCheckable(True)
            nav.addWidget(control)
            self.nav_buttons.append(control)
        nav.addStretch()
        self.user_label=QLabel(f"{store.user['username']}\n{store.user['role'].title()} · local workstation")
        nav.addWidget(self.user_label)
        nav.addWidget(button("Lock workstation",self.lock))
        nav.addWidget(QLabel(f"v{__version__}  •  Offline ready"))
        shell.addWidget(sidebar)
        self.pages=QStackedWidget()
        shell.addWidget(self.pages,1)
        self.build_overview()
        self.build_records()
        self.build_enrollment()
        self.build_templates()
        self.build_jobs()
        self.build_admin()
        self.preview_timer=QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(200)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.idle_timer=QTimer(self)
        self.idle_timer.setInterval(15_000)
        self.idle_timer.timeout.connect(self.check_idle)
        self.idle_timer.start()
        QApplication.instance().installEventFilter(self)
        QShortcut(QKeySequence("Ctrl+S"),self,activated=self.save_record)
        QShortcut(QKeySequence("Ctrl+N"),self,activated=self.new_record)
        QShortcut(QKeySequence("Ctrl+L"),self,activated=self.lock)
        self.refresh_all()
        self.new_record(initial=True)
        self.navigate(0)

    def page(self,heading,description):
        widget=QWidget()
        layout=QVBoxLayout(widget)
        layout.setContentsMargins(30,26,30,24)
        layout.setSpacing(16)
        layout.addWidget(title(heading))
        layout.addWidget(title(description,True))
        self.pages.addWidget(widget)
        return layout

    def guarded(self,action):
        try:
            return action()
        except Exception as exc:
            logging.getLogger(__name__).error("Action failed: %s",type(exc).__name__)
            show_error(self,exc)
            return None

    def navigate(self,index):
        self.pages.setCurrentIndex(index)
        for i,control in enumerate(self.nav_buttons):
            control.setChecked(i==index)
        if index in (0,1,3,4,5):
            self.refresh_all()

    def build_overview(self):
        layout=self.page("A clear view of every credential","Enroll people, review their cards and keep issuance accountable.")
        metrics=QHBoxLayout()
        self.metric_labels={}
        for name in ("Total cardholders","Awaiting approval","Issued cards","Prints to verify"):
            panel=QFrame()
            panel.setProperty("panel",True)
            box=QVBoxLayout(panel)
            box.setContentsMargins(20,22,20,22)
            number=title("0")
            self.metric_labels[name]=number
            box.addWidget(number)
            box.addWidget(title(name,True))
            metrics.addWidget(panel)
        layout.addLayout(metrics)
        banner=QFrame()
        banner.setProperty("panel",True)
        row=QHBoxLayout(banner)
        row.setContentsMargins(24,22,24,22)
        text=QVBoxLayout()
        text.addWidget(title("A new identity starts here"))
        text.addWidget(title("Details → Portrait → Signature → Approval → Print",True))
        row.addLayout(text,1)
        row.addWidget(button("+ Enroll cardholder",self.new_record,True))
        layout.addWidget(banner)
        layout.addWidget(QLabel("RECENT CARDHOLDERS"))
        self.recent_table=table(["Card number","Full name","Department","Valid to","Status"])
        self.recent_table.cellDoubleClicked.connect(lambda row,_:self.open_record(self.recent_table.item(row,0).data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.recent_table,1)
        layout.addWidget(title("Local data • No cloud upload • Administrator approval before printing",True))

    def build_records(self):
        self.record_offset=0
        self.record_page_size=100
        layout=self.page("Cardholders","Find a credential, continue a draft or review its issuance status. Double-click a row to open.")
        bar=QHBoxLayout()
        self.search=QLineEdit()
        self.search.setPlaceholderText("Search by name or card number…")
        self.search.textChanged.connect(self.reset_record_page)
        self.status_filter=QComboBox()
        self.status_filter.addItems(["all","draft","approved","issued","revoked","expired"])
        self.status_filter.currentTextChanged.connect(self.reset_record_page)
        bar.addWidget(self.search,1)
        bar.addWidget(self.status_filter)
        self.import_button=button("Import CSV",self.import_csv)
        self.export_button=button("Export all matches",self.export_csv)
        bar.addWidget(self.import_button)
        bar.addWidget(self.export_button)
        bar.addWidget(button("+ New cardholder",self.new_record,True))
        layout.addLayout(bar)
        self.records_table=table(["Card number","Full name","Department","Valid to","Status"])
        self.records_table.cellDoubleClicked.connect(lambda row,_:self.open_record(self.records_table.item(row,0).data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.records_table,1)
        self.record_count=title("",True)
        pager=QHBoxLayout()
        pager.addWidget(self.record_count,1)
        self.previous_page=button("Previous",lambda:self.move_record_page(-1))
        self.next_page=button("Next",lambda:self.move_record_page(1))
        pager.addWidget(self.previous_page)
        pager.addWidget(self.next_page)
        layout.addLayout(pager)

    def build_enrollment(self):
        layout=self.page("Enrollment","Capture once. Preview both sides. Save a draft before requesting approval.")
        bar=QHBoxLayout()
        self.record_status=QLabel("NEW DRAFT")
        self.record_status.setStyleSheet("color: #087e83; font-weight: 700;")
        bar.addWidget(self.record_status)
        bar.addStretch()
        bar.addWidget(button("New",self.new_record))
        self.save_button=button("Save draft",self.save_record,True)
        bar.addWidget(self.save_button)
        layout.addLayout(bar)
        split=QSplitter()
        layout.addWidget(split,1)
        form_widget=QWidget()
        form_layout=QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0,0,18,0)
        self.form=QFormLayout()
        self.inputs={}
        for key,label in (("full_name","Full name *"),("card_no","Card number *"),("department","Department / class"),("title","Role / course")):
            control=QLineEdit()
            control.setMaxLength(160)
            self.inputs[key]=control
            self.form.addRow(label,control)
            control.textChanged.connect(self.mark_dirty)
        self.expiry=QDateEdit()
        self.expiry.setCalendarPopup(True)
        self.expiry.setDisplayFormat("dd MMM yyyy")
        self.expiry.dateChanged.connect(self.mark_dirty)
        self.form.addRow("Valid to",self.expiry)
        self.template_combo=QComboBox()
        self.template_combo.currentTextChanged.connect(self.mark_dirty)
        self.form.addRow("Card template",self.template_combo)
        form_layout.addLayout(self.form)
        form_layout.addWidget(QLabel("PORTRAIT"))
        self.photo_preview=ImagePreview(140)
        self.photo_preview.setMaximumHeight(160)
        form_layout.addWidget(self.photo_preview)
        photo_actions=QHBoxLayout()
        self.photo_import=button("Import photo",self.import_photo)
        self.camera_button=button("Use camera",self.camera_photo)
        photo_actions.addWidget(self.photo_import)
        photo_actions.addWidget(self.camera_button)
        form_layout.addLayout(photo_actions)
        form_layout.addWidget(QLabel("SIGNATURE"))
        self.signature_preview=ImagePreview(70)
        self.signature_preview.setMaximumHeight(90)
        form_layout.addWidget(self.signature_preview)
        sig_actions=QHBoxLayout()
        self.sig_draw=button("Draw",self.draw_signature)
        self.sig_import=button("Import",self.import_signature)
        self.sig_wacom=button("Wacom pad",self.wacom_signature)
        for control in (self.sig_draw,self.sig_import,self.sig_wacom):
            sig_actions.addWidget(control)
        form_layout.addLayout(sig_actions)
        self.consent=QCheckBox("I have authorization to collect this photo and signature.")
        self.consent.toggled.connect(self.mark_dirty)
        form_layout.addWidget(self.consent)
        form_layout.addStretch()
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_widget)
        split.addWidget(scroll)
        preview_widget=QWidget()
        preview_layout=QVBoxLayout(preview_widget)
        self.side=QComboBox()
        self.side.addItems(["front","back"])
        self.side.currentTextChanged.connect(self.refresh_preview)
        preview_layout.addWidget(self.side)
        self.card_preview=ImagePreview(310)
        preview_layout.addWidget(self.card_preview,1)
        preview_layout.addWidget(title("CR80 · 85.60 × 53.98 mm · 300 DPI",True))
        self.preflight=QLabel("")
        self.preflight.setWordWrap(True)
        preview_layout.addWidget(self.preflight)
        controls=QGridLayout()
        self.approve_button=button("Approve card",lambda:self.change_status("approved"),True)
        self.return_button=button("Return to draft",lambda:self.change_status("draft"))
        self.revoke_button=button("Revoke card",lambda:self.change_status("revoked"))
        self.print_button=button("Print card",self.print_card,True)
        controls.addWidget(self.approve_button,0,0)
        controls.addWidget(self.return_button,0,1)
        controls.addWidget(button("Export PDF",self.export_card),1,0)
        controls.addWidget(self.print_button,1,1)
        controls.addWidget(self.revoke_button,2,1)
        preview_layout.addLayout(controls)
        split.addWidget(preview_widget)
        split.setSizes([480,620])

    def build_templates(self):
        layout=self.page("Template studio","Start with a ready-made layout or import your own background. Both sides stay editable in millimeters.")
        self.templates_table=table(["Template","Organization","Format"])
        self.templates_table.cellDoubleClicked.connect(lambda *_:self.edit_template())
        layout.addWidget(self.templates_table,1)
        actions=QHBoxLayout()
        actions.addWidget(button("Edit selected",self.edit_template))
        actions.addWidget(button("Create from selected",lambda:self.edit_template(copy=True),True))
        actions.addStretch()
        layout.addLayout(actions)
        layout.addWidget(title("Approved templates are protected. Save a new revision to change a design already in use.",True))

    def build_jobs(self):
        layout=self.page("Print history","Submission is not proof of printing. Confirm physical output before handing over a card.")
        self.jobs_table=table(["Created (UTC)","Card number","Printer","Sides","State","Reason"])
        layout.addWidget(self.jobs_table,1)
        actions=QHBoxLayout()
        actions.addWidget(button("Confirm printed",lambda:self.resolve_job("confirmed"),True))
        actions.addWidget(button("Mark not printed",lambda:self.resolve_job("failed")))
        actions.addWidget(button("View saved output",self.view_job))
        actions.addStretch()
        actions.addWidget(button("Refresh",self.refresh_all))
        layout.addLayout(actions)

    def build_admin(self):
        layout=self.page("Administration","Manage operators, safeguard data and inspect the local audit history.")
        actions=QHBoxLayout()
        for label,callback in [("Add user",self.add_user),("Enable / disable user",self.toggle_user),("Change my password",self.change_password),("Create backup",self.backup),("Restore backup",self.restore_backup)]:
            actions.addWidget(button(label,callback))
        layout.addLayout(actions)
        self.users_table=table(["Username","Role","Active"])
        self.users_table.setMaximumHeight(190)
        layout.addWidget(self.users_table)
        self.device_label=QLabel("")
        self.device_label.setWordWrap(True)
        layout.addWidget(self.device_label)
        layout.addWidget(QLabel("AUDIT HISTORY · latest 500 events · UTC"))
        self.audit_table=table(["Time","Operator","Action","Reference","Detail"])
        layout.addWidget(self.audit_table,1)
        layout.addWidget(title("Data is stored locally. Protect this Windows account and use device encryption. Backups contain personal information and are not encrypted by the application.",True))

    def values(self):
        return {**{k:v.text().strip() for k,v in self.inputs.items()},"expires":self.expiry.date().toString("yyyy-MM-dd"),"template":self.template_combo.currentText(),"photo":self.photo,"signature":self.signature,"consent":self.consent.isChecked()}

    def mark_dirty(self,*_):
        if self.loading:
            return
        self.dirty=True
        if hasattr(self,"preview_timer"):
            self.preview_timer.start()

    def discard_ok(self):
        return not self.dirty or QMessageBox.question(self,"Unsaved changes","Discard unsaved enrollment changes?",QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel)==QMessageBox.StandardButton.Discard

    def new_record(self,checked=False,initial=False):
        if not initial and not self.discard_ok():
            return
        self.loading=True
        self.current_record=None
        for control in self.inputs.values():
            control.clear()
        self.expiry.setDate(QDate.currentDate().addYears(1))
        self.photo=self.signature=None
        self.consent.setChecked(False)
        self.loading=False
        self.dirty=False
        self.refresh_preview()
        self.update_permissions()
        if not initial:
            self.navigate(2)
            self.inputs["full_name"].setFocus()

    def open_record(self,record_id):
        if not self.discard_ok():
            return
        def action():
            record=self.store.get_record(record_id)
            self.loading=True
            self.current_record=record
            for key,control in self.inputs.items():
                control.setText(record[key])
            self.expiry.setDate(QDate.fromString(record["expires"],"yyyy-MM-dd"))
            self.template_combo.setCurrentText(record["template"])
            self.photo=record["photo"]
            self.signature=record["signature"]
            self.consent.setChecked(bool(record["consent"]))
            self.loading=False
            self.dirty=False
            self.refresh_preview()
            self.update_permissions()
            self.navigate(2)
        self.guarded(action)

    def save_record(self):
        if self.pages.currentIndex()!=2:
            return
        def action():
            previous=self.current_record or {}
            record_id=self.store.save_record(self.values(),previous.get("id"),previous.get("version"))
            self.current_record=self.store.get_record(record_id)
            self.dirty=False
            self.update_permissions()
            self.statusBar().showMessage("Draft saved.",5000)
            self.refresh_all()
        self.guarded(action)

    def update_permissions(self):
        status=(self.current_record or {}).get("status","draft")
        admin=self.store.user["role"]=="admin"
        editable=status=="draft"
        for control in [*self.inputs.values(),self.expiry,self.template_combo,self.consent,self.photo_import,self.camera_button,self.sig_draw,self.sig_import,self.sig_wacom,self.save_button]:
            control.setEnabled(editable)
        self.record_status.setText(status.upper()+ (" · " + self.current_record["card_no"] if self.current_record else " · UNSAVED"))
        self.approve_button.setEnabled(admin and bool(self.current_record) and status=="draft")
        self.return_button.setEnabled(admin and status=="approved")
        self.revoke_button.setEnabled(admin and status in ("approved","issued"))
        self.print_button.setEnabled(status=="approved" or (admin and status=="issued"))

    def refresh_preview(self,*_):
        if not hasattr(self,"card_preview"):
            return
        values=self.values()
        templates=self.store.templates()
        if values["template"] in templates:
            status=(self.current_record or {}).get("status","draft")
            mark="REVOKED" if status=="revoked" else "DRAFT" if status=="draft" else ""
            try:
                self.card_preview.set_image(render_card(values,templates[values["template"]],self.side.currentText(),mark))
                self.preflight.setText("Before approval: " + "; ".join(self.store.preflight(values)) if self.store.preflight(values) else "Ready for review · Check spelling, portrait, signature and expiry.")
            except DomainError as exc:
                self.preflight.setText(str(exc))
        for raw,preview,label in ((self.photo,self.photo_preview,"No portrait captured"),(self.signature,self.signature_preview,"No signature captured")):
            if raw:
                preview.set_image(QImage.fromData(raw))
            else:
                preview.original=preview.original.__class__()
                preview.setText(label)

    def import_photo(self):
        path,_=QFileDialog.getOpenFileName(self,"Import portrait","","Images (*.png *.jpg *.jpeg)")
        if path:
            self.guarded(lambda:self.crop_photo(load_image(path)))

    def crop_photo(self,image):
        dialog=CropDialog(image,self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.photo=image_bytes(dialog.canvas.result())
            self.mark_dirty()
            self.refresh_preview()

    def camera_photo(self):
        def action():
            dialog=CameraDialog(self)
            if dialog.exec()==QDialog.DialogCode.Accepted and dialog.image is not None:
                self.crop_photo(dialog.image)
        self.guarded(action)

    def draw_signature(self):
        dialog=SignatureDialog(self)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self.signature=image_bytes(dialog.canvas.image)
            self.mark_dirty()
            self.refresh_preview()

    def import_signature(self):
        path,_=QFileDialog.getOpenFileName(self,"Import signature","","Images (*.png *.jpg *.jpeg)")
        if path:
            def action():
                self.signature=image_bytes(normalize_signature(load_image(path)))
                self.mark_dirty()
                self.refresh_preview()
            self.guarded(action)

    def wacom_signature(self):
        def action():
            if not self.inputs["full_name"].text().strip():
                raise DomainError("Enter the cardholder's name before capturing a signature.")
            self.signature=image_bytes(capture_wacom(self.inputs["full_name"].text()))
            self.mark_dirty()
            self.refresh_preview()
        self.guarded(action)

    def saved_record(self):
        if not self.current_record or self.dirty:
            raise DomainError("Save the current draft before continuing.")
        return self.store.get_record(self.current_record["id"])

    def change_status(self,target):
        def action():
            record=self.saved_record()
            reason=""
            if target!="approved":
                reason,ok=QInputDialog.getText(self,"Record reason","Why are you changing this card's status?")
                if not ok:
                    return
            elif QMessageBox.question(self,"Approve credential","Confirm that the portrait, signature, details and expiry are correct?")!=QMessageBox.StandardButton.Yes:
                return
            if target=="approved":
                template=self.store.templates()[record["template"]]
                for side in ("front","back"):
                    render_card(record,template,side)
            self.store.transition(record["id"],target,reason)
            self.open_record(record["id"])
            self.refresh_all()
        self.guarded(action)

    def export_card(self):
        def action():
            record=self.saved_record()
            template=self.store.templates()[record["template"]]
            mark="DRAFT" if record["status"]=="draft" else "REVOKED" if record["status"]=="revoked" else ""
            path,_=QFileDialog.getSaveFileName(self,"Export front and back","credential.pdf","PDF (*.pdf)")
            if path:
                images=[render_card(record,template,side,mark) for side in ("front","back")]
                with atomic_output(path) as temporary:
                    export_pdf(temporary,images)
                with self.store.transaction():
                    self.store.audit("card.exported",record["id"],record["status"])
                self.statusBar().showMessage("Two-page CR80 PDF exported. Print at actual size, without scaling.",8000)
        self.guarded(action)

    def print_card(self):
        def action():
            record=self.saved_record()
            names=printer_names()
            if not names:
                raise DomainError("No printer found. Install the card printer's Windows driver and connect it first.")
            dialog=QDialog(self)
            dialog.setWindowTitle("Print credential")
            form=QFormLayout(dialog)
            printer=QComboBox()
            printer.addItems(names)
            mode=QComboBox()
            mode.addItems(["Front only","Front + back (automatic duplex)","Back only"])
            reason=QLineEdit()
            reason.setPlaceholderText("Required for reprints")
            form.addRow("Printer",printer)
            form.addRow("Sides",mode)
            form.addRow("Reprint reason",reason)
            note=QLabel("Use CR80 stock and a calibrated driver.\nInspect the requested side(s) before confirming issuance.\nAutomatic duplex requires a compatible printer.\nManual card flipping is not automated.")
            note.setWordWrap(True)
            form.addRow(note)
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec()!=QDialog.DialogCode.Accepted:
                return
            device=configured_printer(printer.currentText(),mode.currentIndex()==1)
            template=self.store.templates()[record["template"]]
            images=[render_card(record,template,side) for side in ("front","back")]
            sides=("front","both","back")[mode.currentIndex()]
            job_id=self.store.prepare_job(record["id"],record["version"],image_bytes(images[0]),image_bytes(images[1]),printer.currentText(),reason.text(),sides=sides)
            selected=images if mode.currentIndex()==1 else [images[1] if mode.currentIndex()==2 else images[0]]
            try:
                submit_print(device,selected,job_id)
            except Exception:
                self.store.finish_job(job_id,"uncertain","Submission interrupted; inspect printer before retrying")
                self.navigate(4)
                raise
            self.store.finish_job(job_id,"submitted")
            self.navigate(4)
            QMessageBox.information(self,"Submitted to printer","The job was submitted. Check the physical card, select the job and choose Confirm printed. If nothing printed, inspect the queue before marking it not printed.")
        self.guarded(action)

    def edit_template(self,checked=False,copy=False):
        def action():
            self.store.authorize(admin=True)
            row=self.templates_table.currentRow()
            if row<0:
                row=0
            if self.templates_table.rowCount()==0:
                return
            name=self.templates_table.item(row,0).text()
            body=self.store.templates()[name]
            dialog=TemplateDialog(self.store,name+" / revision" if copy else name,body,self)
            if dialog.exec()==QDialog.DialogCode.Accepted:
                self.refresh_all()
                self.refresh_preview()
        self.guarded(action)

    def selected_job(self):
        row=self.jobs_table.currentRow()
        if row<0:
            raise DomainError("Select a print job first.")
        return self.jobs_table.item(row,0).data(Qt.ItemDataRole.UserRole)

    def resolve_job(self,target):
        def action():
            job_id=self.selected_job()
            prompt="Confirm the physical card was printed correctly." if target=="confirmed" else "Check / cancel the Windows queue first. Why was this card not issued?"
            detail,ok=QInputDialog.getText(self,"Record print outcome",prompt)
            if ok:
                self.store.finish_job(job_id,target,detail)
                if self.current_record and not self.dirty:
                    self.open_record(self.current_record["id"])
                self.navigate(4)
        self.guarded(action)

    def view_job(self):
        def action():
            self.store.authorize()
            job=self.store.db.execute("SELECT * FROM jobs WHERE id=?",(self.selected_job(),)).fetchone()
            dialog=QDialog(self)
            dialog.setWindowTitle("Immutable print snapshot · "+job["status"])
            dialog.resize(1050,430)
            layout=QHBoxLayout(dialog)
            for side in ("front","back"):
                view=ImagePreview(300)
                view.set_image(QImage.fromData(job[side]))
                layout.addWidget(view)
            dialog.exec()
        self.guarded(action)

    def import_csv(self):
        def action():
            from .importing import read_csv
            self.store.authorize(admin=True)
            path,_=QFileDialog.getOpenFileName(self,"Import cardholder drafts","","CSV (*.csv)")
            if not path:
                return
            dialog=CSVImportDialog(self.store,read_csv(path),self)
            if dialog.exec()==QDialog.DialogCode.Accepted:
                ids=self.store.import_drafts(dialog.rows,dialog.template.currentText())
                self.record_offset=0
                self.refresh_all()
                QMessageBox.information(self,"Drafts imported",f"{len(ids)} cardholders imported as drafts. Open each record to capture its portrait, signature and authorization before approval.")
        self.guarded(action)

    def export_csv(self):
        def action():
            self.store.authorize(admin=True)
            path,_=QFileDialog.getSaveFileName(self,"Export all matching cardholders","cardholders.csv","CSV (*.csv)")
            if path:
                keys=["card_no","full_name","department","expires","status"]
                count=0
                with atomic_output(path) as temporary:
                    with temporary.open("w",newline="",encoding="utf-8-sig") as output:
                        writer=csv.writer(output)
                        writer.writerow(keys)
                        for row in self.store.export_records(self.search.text(),self.status_filter.currentText()):
                            # Prevent spreadsheet formula interpretation of untrusted fields.
                            writer.writerow([("'"+str(row[k])) if str(row[k]).lstrip().startswith(("=","+","-","@")) else row[k] for k in keys])
                            count+=1
                with self.store.transaction():
                    self.store.audit("records.exported",detail=f"{count} rows")
                self.statusBar().showMessage(f"Exported all {count} matching cardholders.",8000)
        self.guarded(action)

    def add_user(self):
        def action():
            self.store.authorize(admin=True)
            dialog=QDialog(self)
            dialog.setWindowTitle("Create local account")
            form=QFormLayout(dialog)
            username=QLineEdit()
            password=QLineEdit()
            password.setEchoMode(QLineEdit.EchoMode.Password)
            role=QComboBox()
            role.addItems(["operator","admin"])
            form.addRow("Username",username)
            form.addRow("Password (12+ characters)",password)
            form.addRow("Role",role)
            buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            form.addRow(buttons)
            if dialog.exec()==QDialog.DialogCode.Accepted:
                self.store.create_user(username.text(),password.text(),role.currentText())
                self.refresh_all()
        self.guarded(action)

    def toggle_user(self):
        def action():
            self.store.authorize(admin=True)
            row=self.users_table.currentRow()
            if row<0:
                raise DomainError("Select an account first.")
            user_id=self.users_table.item(row,0).data(Qt.ItemDataRole.UserRole)
            active=self.users_table.item(row,2).text()=="1"
            self.store.set_active(user_id,not active)
            self.refresh_all()
        self.guarded(action)

    def change_password(self):
        def action():
            current,ok=QInputDialog.getText(self,"Change password","Current password",QLineEdit.EchoMode.Password)
            if not ok:
                return
            replacement,ok=QInputDialog.getText(self,"Change password","New password (12+ characters)",QLineEdit.EchoMode.Password)
            if ok:
                self.store.change_password(current,replacement)
                QMessageBox.information(self,"Password updated","Your new password is active.")
        self.guarded(action)

    def backup(self):
        def action():
            self.store.authorize(admin=True)
            path,_=QFileDialog.getSaveFileName(self,"Save backup","credential-backup.zip","Backup (*.zip)")
            if path:
                self.store.backup(path)
                QMessageBox.information(self,"Backup created","Database, templates, photographs, signatures and print history are included. Store this unencrypted archive on a protected drive.")
        self.guarded(action)

    def restore_backup(self):
        def action():
            self.store.authorize(admin=True)
            archive,_=QFileDialog.getOpenFileName(self,"Choose backup","","Backup (*.zip)")
            if not archive:
                return
            folder=QFileDialog.getExistingDirectory(self,"Choose an empty recovery folder")
            if folder:
                Store.restore(archive,folder)
                QMessageBox.information(self,"Backup verified and restored",f"Recovered into {folder}.\nClose this application and launch CredentialStudio.exe with --data-dir followed by this folder path. The current workspace is unchanged.")
        self.guarded(action)

    def reset_record_page(self,*_):
        self.record_offset=0
        self.refresh_records()

    def move_record_page(self,direction):
        self.record_offset=max(0,self.record_offset+direction*self.record_page_size)
        self.refresh_records()

    def refresh_records(self,*_):
        if not hasattr(self,"records_table"):
            return
        count=self.store.record_count(self.search.text(),self.status_filter.currentText())
        self.record_offset=min(self.record_offset,max(0,((count-1)//self.record_page_size)*self.record_page_size))
        rows=self.store.records(self.search.text(),self.status_filter.currentText(),limit=self.record_page_size,offset=self.record_offset)
        populate(self.records_table,rows,["card_no","full_name","department","expires","status"])
        first=self.record_offset+1 if count else 0
        self.record_count.setText(f"Showing {first}–{self.record_offset+len(rows)} of {count} matches")
        self.previous_page.setEnabled(self.record_offset>0)
        self.next_page.setEnabled(self.record_offset+len(rows)<count)

    def refresh_all(self):
        self.store.authorize()
        records=self.store.records(limit=8)
        populate(self.recent_table,records[:8],["card_no","full_name","department","expires","status"])
        self.refresh_records()
        counts=dict(self.store.db.execute("SELECT status,count(*) FROM records GROUP BY status").fetchall())
        pending=self.store.db.execute("SELECT count(*) FROM jobs WHERE status IN ('prepared','submitted','uncertain')").fetchone()[0]
        for key,value in zip(self.metric_labels,[sum(counts.values()),counts.get("draft",0),counts.get("issued",0),pending]):
            self.metric_labels[key].setText(str(value))
        templates=self.store.templates()
        selected=self.template_combo.currentText()
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        self.template_combo.addItems(list(templates))
        if selected in templates:
            self.template_combo.setCurrentText(selected)
        self.template_combo.blockSignals(False)
        self.templates_table.setRowCount(len(templates))
        for row,(name,body) in enumerate(templates.items()):
            for column,text in enumerate((name,body["organization"],"CR80 · front + back")):
                self.templates_table.setItem(row,column,QTableWidgetItem(text))
        jobs=[dict(row) for row in self.store.db.execute("SELECT j.id,j.created_at,r.card_no,j.printer,j.status,j.reason,j.snapshot FROM jobs j JOIN records r ON j.record_id=r.id ORDER BY j.created_at DESC,j.id DESC LIMIT 500")]
        for job in jobs:
            job["sides"]=json.loads(job.pop("snapshot")).get("sides","Legacy: see audit")
        populate(self.jobs_table,jobs,["created_at","card_no","printer","sides","status","reason"])
        admin=self.store.user["role"]=="admin"
        self.import_button.setEnabled(admin)
        self.export_button.setEnabled(admin)
        if self.store.user["role"]=="admin":
            users=self.store.db.execute("SELECT id,username,role,active FROM users ORDER BY username").fetchall()
            audit=self.store.db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 500").fetchall()
            populate(self.users_table,users,["username","role","active"])
            populate(self.audit_table,audit,["at","actor","action","target","detail"])
        else:
            self.users_table.setRowCount(0)
            self.audit_table.setRowCount(0)
        self.device_label.setText("Detected printers: " + (", ".join(printer_names()) or "none") + "\nWacom: hardware and licensed vendor SDK required; status checked during capture.")
        self.statusBar().showMessage(f"{self.store.user['username']} · Local workspace · {self.store.folder}")

    def eventFilter(self,obj,event):
        if event.type() in (QEvent.Type.KeyPress,QEvent.Type.MouseButtonPress,QEvent.Type.MouseMove):
            self.last_activity=time.monotonic()
        return False

    def check_idle(self):
        if time.monotonic()-self.last_activity>600 and not self.locking:
            # Close capture dialogs before hiding sensitive content.
            modal=QApplication.activeModalWidget()
            if modal and isinstance(modal,QDialog):
                modal.reject()
            self.lock()

    def lock(self):
        if self.locking:
            return
        self.locking=True
        with self.store.transaction():
            self.store.audit("session.locked")
        username=self.store.user["username"]
        self.store.user=None
        self.hide()
        dialog=LoginDialog(self.store)
        dialog.username.setText(username)
        dialog.username.setReadOnly(True)
        if dialog.exec()!=QDialog.DialogCode.Accepted:
            QApplication.instance().quit()
            return
        # Reauthentication is bound to the same operator; preserve unsaved work.
        self.user_label.setText(f"{self.store.user['username']}\n{self.store.user['role'].title()} · local workstation")
        self.refresh_all()
        self.update_permissions()
        self.show()
        self.last_activity=time.monotonic()
        self.locking=False

    def closeEvent(self,event):
        if self.discard_ok():
            event.accept()
        else:
            event.ignore()


def main():
    parser=argparse.ArgumentParser(description="Credential Studio desktop issuance workstation")
    parser.add_argument("--data-dir",type=Path,default=data_directory())
    parser.add_argument("--smoke-test",action="store_true",help="Verify packaged Qt UI and rendering without modifying user data")
    args=parser.parse_args()
    app=QApplication(sys.argv[:1])
    app.setApplicationName("Credential Studio")
    app.setOrganizationName("CredentialStudio")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    if args.smoke_test:
        image=render_card({"full_name":"Build verification"},next(iter(default_templates().values())))
        return 0 if not image.isNull() else 1
    args.data_dir.mkdir(parents=True,exist_ok=True)
    lock=QLockFile(str(args.data_dir/"workstation.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.warning(None,"Already running","This workspace is open in another Credential Studio instance.")
        return 1
    handler=RotatingFileHandler(args.data_dir/"application.log",maxBytes=1_000_000,backupCount=3)
    logging.basicConfig(level=logging.WARNING,handlers=[handler],format="%(asctime)s %(levelname)s %(message)s")
    def exception_hook(kind,value,traceback):
        logging.error("Unhandled error: %s",kind.__name__)
        QMessageBox.critical(None,"Unexpected problem","The action could not be completed. Reopen the record and inspect print history before retrying. Diagnostic logs are in the data folder.")
    sys.excepthook=exception_hook
    store=None
    try:
        store=Store(args.data_dir)
        login=LoginDialog(store)
        if login.exec()!=QDialog.DialogCode.Accepted:
            return 0
        if not store.templates() and store.user["role"]=="admin":
            for name,template in default_templates().items():
                store.save_template(name,template)
        store.recover_jobs()
        window=MainWindow(store)
        window.show()
        return app.exec()
    finally:
        if store:
            store.close()
        lock.unlock()


if __name__=="__main__":
    raise SystemExit(main())
