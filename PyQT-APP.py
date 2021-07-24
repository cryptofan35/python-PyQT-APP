#!/usr/bin/python3
# -*- coding:utf-8 -*-
import csv, codecs
import os
import pandas as pd
from PyQt5 import QtPrintSupport
from PyQt5.QtGui import (QImage, QPainter, QIcon, QKeySequence, QTextCursor, QPalette,
                         QCursor, QDropEvent, QTextDocument, QTextTableFormat, QColor, QBrush)
from PyQt5.QtCore import (QFile, QSettings, Qt, QFileInfo, QItemSelectionModel, QDir,
                          QMetaObject, QAbstractTableModel, QModelIndex, QVariant)
from PyQt5.QtWidgets import (QMainWindow, QAction, QWidget, QLineEdit, QMessageBox, QAbstractItemView, QApplication,
                             QTableWidget, QTableWidgetItem, QGridLayout, QFileDialog, QMenu, QInputDialog, QPushButton)


class TableWidgetDragRows(QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)

        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setDragDropMode(QAbstractItemView.InternalMove)

    def dropEvent(self, event: QDropEvent):
        if not event.isAccepted() and event.source() == self:
            drop_row = self.drop_on(event)

            rows = sorted(set(item.row() for item in self.selectedItems()))
            rows_to_move = [
                [QTableWidgetItem(self.item(row_index, column_index)) for column_index in range(self.columnCount())]
                for row_index in rows]
            for row_index in reversed(rows):
                self.removeRow(row_index)
                if row_index < drop_row:
                    drop_row -= 1

            for row_index, data in enumerate(rows_to_move):
                row_index += drop_row
                self.insertRow(row_index)
                for column_index, column_data in enumerate(data):
                    self.setItem(row_index, column_index, column_data)
            event.accept()
            for row_index in range(len(rows_to_move)):
                self.item(drop_row + row_index, 0).setSelected(True)
                self.item(drop_row + row_index, 1).setSelected(True)
        super().dropEvent(event)

    def drop_on(self, event):
        index = self.indexAt(event.pos())
        if not index.isValid():
            return self.rowCount()

        return index.row() + 1 if self.is_below(event.pos(), index) else index.row()

    def is_below(self, pos, index):
        rect = self.visualRect(index)
        margin = 2
        if pos.y() - rect.top() < margin:
            return False
        elif rect.bottom() - pos.y() < margin:
            return True
        # noinspection PyTypeChecker
        return rect.contains(pos, True) and not (
                    int(self.model().flags(index)) & Qt.ItemIsDropEnabled) and pos.y() >= rect.center().y()


class MyWindow(QMainWindow):
    def __init__(self, aPath, parent=None):
        super(MyWindow, self).__init__(parent)
        # QIcon.setThemeName('Mint-Y')
        QMetaObject.connectSlotsByName(self)
        self.root = os.path.dirname(sys.argv[0])
        self.logo = os.path.join(self.root, "logo_48.png")
        self.setWindowIcon(QIcon.fromTheme(self.logo))
        self.delimit = '\t'
        self.mycolumn = 0
        self.MaxRecentFiles = 5
        self.windowList = []
        self.recentFileActs = []
        self.settings = QSettings('Axel Schneider', 'CSVEditor')
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.isChanged = False
        self.fileName = ""
        self.fname = "Liste"
        self.mytext = ""
        self.colored = False
        self.copiedRow = []
        self.copiedColumn = []
        self.hasHeaders = False
        ### QTableView seetings
        self.tableView = TableWidgetDragRows()
        self.tableView.setGridStyle(1)
        self.tableView.setCornerButtonEnabled(False)
        self.tableView.setShowGrid(True)
        self.tableView.horizontalHeader().setBackgroundRole(QPalette.Window)
        #        self.tableView.setSelectionBehavior (QAbstractItemView.SelectRows )
        self.tableView.selectionModel().selectionChanged.connect(self.makeAllWhite)
        self.tableView.itemClicked.connect(self.getItem)
        self.tableView.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.tableView.cellChanged.connect(self.finishedEdit)
        self.tableView.setDropIndicatorShown(True)

        self.findfield = QLineEdit()
        findAction = QAction(QIcon.fromTheme("edit-find"), "find", self, triggered=self.findText)
        self.findfield.addAction(findAction, 0)
        self.findfield.setPlaceholderText("find (RETURN)")
        self.findfield.setToolTip("press RETURN to find all matches")
        self.findfield.setFixedWidth(150)
        self.findfield.returnPressed.connect(self.findText)

        self.replacefield = QLineEdit()
        replaceAction = QAction(QIcon.fromTheme("edit-find-replace"), "replace", self, triggered=self.replaceText)
        self.replacefield.addAction(replaceAction, 0)
        self.replacefield.setPlaceholderText("replace")
        self.replacefield.setToolTip("replace (RETURN to replace first)")
        self.replacefield.setFixedWidth(150)
        self.replacefield.returnPressed.connect(self.replaceText)

        self.btnreplace = QPushButton("replace all")
        self.btnreplace.setIcon(QIcon.fromTheme("gtk-find-and-replace"))
        self.btnreplace.clicked.connect(self.replaceTextAll)
        self.btnreplace.setToolTip("replace all")
        self.btnreplace.setFixedWidth(100)

        self.editLine = QLineEdit()
        self.editLine.setToolTip("edit and press ENTER")
        self.editLine.setStatusTip("edit and press ENTER")
        self.editLine.returnPressed.connect(self.updateCell)

        grid = QGridLayout()
        grid.setSpacing(1)
        grid.addWidget(self.editLine, 0, 0)
        grid.addWidget(self.findfield, 0, 1)
        grid.addWidget(self.replacefield, 0, 2)
        grid.addWidget(self.btnreplace, 0, 3)
        grid.addWidget(self.tableView, 1, 0, 1, 4)

        mywidget = QWidget()
        mywidget.setLayout(grid)
        self.setCentralWidget(mywidget)
        self.isChanged = False
        self.createActions()
        self.createMenuBar()
        self.setStyleSheet(stylesheet(self))
        self.readSettings()
        self.msg("Welcome to CSV Reader")

        if len(sys.argv) > 1:
            print(sys.argv[1])
            self.fileName = sys.argv[1]
            self.loadCsvOnOpen(self.fileName)
            self.msg(self.fileName + "loaded")
        else:
            self.msg("Ready")
            self.addRow()
            self.isChanged = False

    def changeSelection(self):
        self.tableView.setSelectionMode(QAbstractItemView.ExtendedSelection)

    def updateCell(self):
        if self.tableView.selectionModel().hasSelection():
            row = self.selectedRow()
            column = self.selectedColumn()
            newtext = QTableWidgetItem(self.editLine.text())
            self.tableView.setItem(row, column, newtext)

    def getItem(self):
        item = self.tableView.selectedItems()[0]
        row = self.selectedRow()
        column = self.selectedColumn()
        if not item == None:
            name = item.text()
        else:
            name = ""
        self.msg("'" + name + "' on Row " + str(row + 1) + " Column " + str(column + 1))
        self.editLine.setText(name)

    def selectedRow(self):
        if self.tableView.selectionModel().hasSelection():
            row = self.tableView.selectionModel().selectedIndexes()[0].row()
            return int(row)

    def selectedColumn(self):
        column = self.tableView.selectionModel().selectedIndexes()[0].column()
        return int(column)

    def findText(self):
        self.findTableItems()
        self.changeSelection()

    def findTableItems(self):
        findText = self.findfield.text()
        self.tableView.clearSelection()
        items = self.tableView.findItems(findText, Qt.MatchContains)
        if items:
            self.colored = True
            self.makeAllWhite()
            for item in items:
                item.setBackground(Qt.yellow)
            self.colored = True
            self.isChanged = False

    def findThis(self):
        self.tableView.clearSelection()
        items = self.tableView.findItems(self.mytext, Qt.MatchContains)
        if items:
            self.colored = True
            self.makeAllWhite()
            for item in items:
                item.setBackground(Qt.yellow)
                item.setForeground(Qt.blue)
            self.colored = True
            self.isChanged = False

    def msgbox(self, message):
        QMessageBox.warning(self, "Message", message)

    def createMenuBar(self):
        bar = self.menuBar()
        self.filemenu = bar.addMenu("File")
        self.separatorAct = self.filemenu.addSeparator()
        self.filemenu.addAction(QIcon.fromTheme("document-new"), "New", self.newCsv, QKeySequence.New)
        self.filemenu.addAction(QIcon.fromTheme("document-open"), "Open", self.loadCsv, QKeySequence.Open)
        self.filemenu.addAction(QIcon.fromTheme("document-save"), "Save", self.saveOnQuit, QKeySequence.Save)
        self.filemenu.addAction(QIcon.fromTheme("document-save-as"), "Save as ...", self.writeCsv, QKeySequence.SaveAs)
        self.filemenu.addSeparator()
        self.filemenu.addAction(QIcon.fromTheme("document-print-preview"), "Print Preview", self.handlePreview,
                                "Shift+Ctrl+P")
        self.filemenu.addAction(QIcon.fromTheme("document-print"), "Print", self.handlePrint, QKeySequence.Print)
        self.filemenu.addSeparator()
        for i in range(self.MaxRecentFiles):
            self.filemenu.addAction(self.recentFileActs[i])
        self.updateRecentFileActions()
        self.filemenu.addSeparator()
        self.clearRecentAct = QAction("clear Recent Files List", self, triggered=self.clearRecentFiles)
        self.clearRecentAct.setIcon(QIcon.fromTheme("edit-clear"))
        self.filemenu.addAction(self.clearRecentAct)
        self.filemenu.addSeparator()
        self.filemenu.addAction(QIcon.fromTheme("application-exit"), "Exit", self.handleQuit, QKeySequence.Quit)

        self.editmenu = bar.addMenu("Edit")
        self.editmenu.addAction(self.actionUndo)
        self.editmenu.addAction(self.actionRedo)
        self.editmenu.addSeparator()
        self.editmenu.addAction(QIcon.fromTheme("edit"), "first row to headers", self.setHeaders)
        self.editmenu.addAction(QIcon.fromTheme("edit"), "headers to first row", self.setHeadersToFirstRow)
        self.editmenu.addSeparator()
        self.editmenu.addAction(QIcon.fromTheme("edit-copy"), "copy Cell", self.copyByContext, QKeySequence.Copy)
        self.editmenu.addAction(QIcon.fromTheme("edit-paste"), "paste Cell", self.pasteByContext, QKeySequence.Paste)
        self.editmenu.addAction(QIcon.fromTheme("edit-cut"), "cut Cell", self.cutByContext, QKeySequence.Cut)
        self.editmenu.addAction(QIcon.fromTheme("edit-delete"), "delete Cell", self.deleteCell, QKeySequence.Delete)
        self.editmenu.addSeparator()
        self.editmenu.addAction(QIcon.fromTheme("edit-copy"), "copy Row", self.copyRow)
        self.editmenu.addAction(QIcon.fromTheme("edit-paste"), "paste Row", self.pasteRow)
        self.editmenu.addSeparator()
        self.editmenu.addAction(QIcon.fromTheme("edit-copy"), "copy Column", self.copyColumn)
        self.editmenu.addAction(QIcon.fromTheme("edit-paste"), "paste Column", self.pasteColumn)
        self.editmenu.addSeparator()
        self.editmenu.addAction(QIcon.fromTheme("add"), "add Row", self.addRow)
        self.editmenu.addAction(QIcon.fromTheme("edit-delete"), "remove Row", self.removeRow)
        self.editmenu.addSeparator()
        self.editmenu.addAction(QIcon.fromTheme("add"), "add Column", self.addColumn)
        self.editmenu.addAction(QIcon.fromTheme("edit-delete"), "remove Column", self.removeColumn)
        self.editmenu.addSeparator()
        self.editmenu.addAction(QIcon.fromTheme("edit-clear"), "clear List", self.clearList)
        self.editmenu.addSeparator()
        self.editmenu.addAction(QIcon.fromTheme("pane-show-symbolic"), "toggle horizontal Headers",
                                self.toggleHorizHeaders)
        self.editmenu.addAction(QIcon.fromTheme("pane-hide-symbolic"), "toggle vertical Headers",
                                self.toggleVertHeaders)
        self.editmenu.addAction(self.whiteAction)

    def deleteCell(self):
        row = self.selectedRow()
        col = self.selectedColumn()
        self.tableView.takeItem(row, col)

    def toggleHorizHeaders(self):
        if self.tableView.horizontalHeader().isVisible():
            self.tableView.horizontalHeader().setVisible(False)
        else:
            self.tableView.horizontalHeader().setVisible(True)

    def toggleVertHeaders(self):
        if self.tableView.verticalHeader().isVisible():
            self.tableView.verticalHeader().setVisible(False)
        else:
            self.tableView.verticalHeader().setVisible(True)

    def createActions(self):
        self.actionUndo = QAction(self)
        icon = QIcon.fromTheme("edit-undo")
        self.actionUndo.setText("Undo")
        self.actionUndo.setIcon(icon)
        self.actionUndo.setObjectName("actionUndo")
        self.actionUndo.setShortcut(QKeySequence.Undo)
        self.actionRedo = QAction(self)
        icon = QIcon.fromTheme("edit-redo")
        self.actionRedo.setText("Redo")
        self.actionRedo.setIcon(icon)
        self.actionRedo.setObjectName("actionRedo")
        self.actionRedo.setShortcut(QKeySequence.Redo)
        # all items white BG
        self.whiteAction = QAction(QIcon.fromTheme("pane-hide-symbolic"), "all items white background", self)
        self.whiteAction.triggered.connect(lambda: self.makeAllWhite())
        for i in range(self.MaxRecentFiles):
            self.recentFileActs.append(
                QAction(self, visible=False,
                        triggered=self.openRecentFile))

    def openRecentFile(self):
        action = self.sender()
        if action:
            if self.isChanged == True:
                quit_msg = "<b>The Document was changed.<br>Do you want to save changes?</ b>"
                reply = QMessageBox.question(self, 'Save Confirmation',
                                             quit_msg, QMessageBox.Yes, QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.saveOnQuit()
            file = action.data()
            if QFile.exists(file):
                self.loadCsvOnOpen(file)
            else:
                self.msg("File not exists")

    def handleQuit(self):
        quit()

    def loadCsvOnOpen(self, fileName):
        if fileName:

            df = pd.read_csv(fileName, header=None, delimiter=',', keep_default_na=False, error_bad_lines=False)
            header = df.iloc[0]

            ### ask for header
            ret = QMessageBox.question(self, "CSV Viewer",
                                       "use first row as header?\n\n" + str(header.values),
                                       QMessageBox.Ok | QMessageBox.No, defaultButton=QMessageBox.Ok)
            if ret == QMessageBox.Ok:
                df = df[1:]

                self.tableView.setColumnCount(len(df.columns))
                self.tableView.setRowCount(len(df.index))

                for i in range(len(df.index)):
                    for j in range(len(df.columns)):
                        self.tableView.setItem(i, j, QTableWidgetItem(str(df.iat[i, j])))

                for j in range(len(df.columns)):
                    m = QTableWidgetItem(header[j])
                    self.tableView.setHorizontalHeaderItem(j, m)

                self.hasHeaders = True

            else:
                self.tableView.setColumnCount(len(df.columns))
                self.tableView.setRowCount(len(df.index))

                for i in range(len(df.index)):
                    for j in range(len(df.columns)):
                        self.tableView.setItem(i, j, QTableWidgetItem(str(df.iat[i, j])))

                for j in range(self.tableView.columnCount()):
                    m = QTableWidgetItem(str(j))
                    self.tableView.setHorizontalHeaderItem(j, m)

                self.hasHeaders = False

            self.tableView.selectRow(0)
            self.isChanged = False
            self.setCurrentFile(fileName)
            self.tableView.resizeColumnsToContents()
            self.tableView.resizeRowsToContents()
            self.msg(fileName + " loaded")

    def loadCsv(self):
        if self.isChanged == True:
            quit_msg = "<b>The Document was changed.<br>Do you want to save changes?</ b>"
            reply = QMessageBox.question(self, 'Save Confirmation',
                                         quit_msg, QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.saveOnQuit()
        fileName, _ = QFileDialog.getOpenFileName(self, "Open CSV",
                                                  (QDir.homePath() + "/Dokumente/CSV"), "CSV (*.csv *.tsv *.txt)")
        if fileName:
            self.loadCsvOnOpen(fileName)

    def newCsv(self):
        if self.isChanged == True:
            quit_msg = "<b>The Document was changed.<br>Do you want to save changes?</ b>"
            reply = QMessageBox.question(self, 'Save Confirmation',
                                         quit_msg, QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.saveOnQuit()
        i = 0
        for row in range(self.tableView.rowCount()):
            self.tableView.removeRow(i)
            i = + 1
        j = 0
        for column in range(self.tableView.columnCount()):
            self.tableView.removeColumn(j)
            j = + 1
        self.tableView.clearContents()

        newItem = QTableWidgetItem("0")
        self.tableView.setHorizontalHeaderItem(0, newItem)

        self.fileName = ""
        self.setWindowTitle('New' + "[*]")
        self.isChanged = False
        self.hasHeaders = False

    def writeCsv(self):
        print(self.hasHeaders)
        path, _ = QFileDialog.getSaveFileName(self, 'Save File', QDir.homePath() + "/export.csv",
                                              "CSV Files(*.csv *.txt)")
        if path:
            if self.hasHeaders:
                self.setHeadersToFirstRow()
            with open(path, 'w') as stream:
                print("saving", path)
                writer = csv.writer(stream, delimiter=self.delimit)
                for row in range(self.tableView.rowCount()):
                    rowdata = []
                    for column in range(self.tableView.columnCount()):
                        item = self.tableView.item(row, column)
                        if item is not None:
                            rowdata.append(item.text())
                        else:
                            rowdata.append('')
                    writer.writerow(rowdata)
        self.isChanged = False
        self.setCurrentFile(path)
        self.setHeaders()

    def handlePrint(self):
        if self.tableView.rowCount() == 0:
            self.msg("no rows")
        else:
            dialog = QtPrintSupport.QPrintDialog()
            if dialog.exec_() == QDialog.Accepted:
                self.handlePaintRequest(dialog.printer())
                self.msg("Document printed")

    def handlePreview(self):
        if self.tableView.rowCount() == 0:
            self.msg("no rows")
        else:
            dialog = QtPrintSupport.QPrintPreviewDialog()
            dialog.setFixedSize(1000, 700)
            dialog.paintRequested.connect(self.handlePaintRequest)
            dialog.exec_()
            self.msg("Print Preview closed")

    def handlePaintRequest(self, printer):
        printer.setDocName(self.fname)
        document = QTextDocument()
        cursor = QTextCursor(document)
        model = self.tableView.model()
        tableFormat = QTextTableFormat()
        tableFormat.setBorder(0.2)
        tableFormat.setBorderStyle(3)
        tableFormat.setCellSpacing(0);
        tableFormat.setTopMargin(0);
        tableFormat.setCellPadding(4)
        table = cursor.insertTable(model.rowCount() + 1, model.columnCount(), tableFormat)
        model = self.tableView.model()
        ### get headers
        myheaders = []
        for i in range(0, model.columnCount()):
            myheader = model.headerData(i, Qt.Horizontal)
            cursor.insertText(str(myheader))
            cursor.movePosition(QTextCursor.NextCell)
        ### get cells
        for row in range(0, model.rowCount()):
            for col in range(0, model.columnCount()):
                index = model.index(row, col)
                cursor.insertText(str(index.data()))
                cursor.movePosition(QTextCursor.NextCell)
        document.print_(printer)

    def removeRow(self):
        if self.tableView.rowCount() > 0:
            row = self.selectedRow()
            tableView.removeRow(row)
            self.isChanged = True

    def addRow(self):
        if self.tableView.rowCount() > 0:
            if self.tableView.selectionModel().hasSelection():
                row = self.selectedRow()
                item = QTableWidgetItem("")
                self.tableView.insertRow(row, 0, item)
            else:
                row = 0
                item = QTableWidgetItem("")
                self.tableView.insertRow(row, 0, item)
                self.tableView.selectRow(0)
        else:
            self.tableView.setRowCount(1)
        if self.tableView.columnCount() == 0:
            self.addColumn()
            self.tableView.selectRow(0)
        self.isChanged = True

    def clearList(self):
        self.tableView.clear()
        self.isChanged = True

    def removeColumn(self):
        self.tableView.removeColumn(self.selectedColumn())
        self.isChanged = True

    def addColumn(self):
        count = self.tableView.columnCount()
        self.tableView.setColumnCount(count + 1)
        self.tableView.resizeColumnsToContents()
        self.isChanged = True
        if self.tableView.rowCount() == 0:
            self.addRow()
            self.tableView.selectRow(0)

    def makeAllWhite(self):
        if self.colored == True:
            for row in range(self.tableView.rowCount()):
                for column in range(self.tableView.columnCount()):
                    item = self.tableView.item(row, column)
                    if item is not None:
                        item.setForeground(Qt.black)
                        item.setBackground(QColor("#e1e1e1"))
        self.colored = False

    def finishedEdit(self):
        self.isChanged = True

    def contextMenuEvent(self, event):
        self.menu = QMenu(self)
        if self.tableView.selectionModel().hasSelection():
            # copy
            copyAction = QAction(QIcon.fromTheme("edit-copy"), 'Copy Cell', self)
            copyAction.triggered.connect(lambda: self.copyByContext())
            # paste
            pasteAction = QAction(QIcon.fromTheme("edit-paste"), 'Paste Cell', self)
            pasteAction.triggered.connect(lambda: self.pasteByContext())
            # cut
            cutAction = QAction(QIcon.fromTheme("edit-cut"), 'Cut Cell', self)
            cutAction.triggered.connect(lambda: self.cutByContext())
            # delete selected Row
            removeAction = QAction(QIcon.fromTheme("edit-delete"), 'delete Row', self)
            removeAction.triggered.connect(lambda: self.deleteRowByContext(event))
            # add Row after
            addAction = QAction(QIcon.fromTheme("add"), 'insert new Row after', self)
            addAction.triggered.connect(lambda: self.addRowByContext(event))
            # add Row before
            addAction2 = QAction(QIcon.fromTheme("add"), 'insert new Row before', self)
            addAction2.triggered.connect(lambda: self.addRowByContext2(event))
            # add Column before
            addColumnBeforeAction = QAction(QIcon.fromTheme("add"), 'insert new Column before', self)
            addColumnBeforeAction.triggered.connect(lambda: self.addColumnBeforeByContext(event))
            # add Column after
            addColumnAfterAction = QAction(QIcon.fromTheme("add"), 'insert new Column after', self)
            addColumnAfterAction.triggered.connect(lambda: self.addColumnAfterByContext(event))
            # delete Column
            deleteColumnAction = QAction(QIcon.fromTheme("edit-delete"), 'delete Column', self)
            deleteColumnAction.triggered.connect(lambda: self.deleteColumnByContext(event))
            # replace all
            row = self.selectedRow()
            col = self.selectedColumn()
            myitem = self.tableView.item(row, col)
            if myitem is not None:
                self.mytext = myitem.text()
            replaceThisAction = QAction(QIcon.fromTheme("edit-find-and-replace"),
                                        "replace all occurrences of '" + self.mytext + "'", self)
            replaceThisAction.triggered.connect(lambda: self.replaceThis())
            # find all
            findThisAction = QAction(QIcon.fromTheme("edit-find"), "find all rows contains '" + self.mytext + "'", self)
            findThisAction.triggered.connect(lambda: self.findThis())
            ###
            self.menu.addAction(copyAction)
            self.menu.addAction(pasteAction)
            self.menu.addAction(cutAction)
            self.menu.addSeparator()
            self.menu.addAction(QIcon.fromTheme("edit-delete"), "delete", self.deleteCell, QKeySequence.Delete)
            self.menu.addSeparator()
            self.menu.addAction(QIcon.fromTheme("edit-copy"), "copy Row", self.copyRow)
            self.menu.addAction(QIcon.fromTheme("edit-paste"), "paste Row", self.pasteRow)
            self.menu.addSeparator()
            self.menu.addAction(QIcon.fromTheme("edit-copy"), "copy Column", self.copyColumn)
            self.menu.addAction(QIcon.fromTheme("edit-paste"), "paste Column", self.pasteColumn)
            self.menu.addSeparator()
            self.menu.addAction(addAction)
            self.menu.addAction(addAction2)
            self.menu.addSeparator()
            self.menu.addAction(addColumnBeforeAction)
            self.menu.addAction(addColumnAfterAction)
            self.menu.addSeparator()
            self.menu.addAction(removeAction)
            self.menu.addAction(deleteColumnAction)
            self.menu.addSeparator()
            self.menu.addAction(replaceThisAction)
            self.menu.addAction(findThisAction)
            self.menu.addSeparator()
            self.menu.addAction(self.whiteAction)
            self.menu.popup(QCursor.pos())

    def replaceThis(self):
        row = self.selectedRow()
        col = self.selectedColumn()
        myitem = self.tableView.item(row, col)
        if myitem is not None:
            mytext = myitem.text()
            dlg = QInputDialog()
            newtext, ok = dlg.getText(self, "Replace all", "replace all <b>" + mytext + " </b> with:", QLineEdit.Normal,
                                      "", Qt.Dialog)
            if ok:
                items = self.tableView.findItems(mytext, Qt.MatchExactly)
                if items:
                    for item in items:
                        newItem = QTableWidgetItem(newtext)
                        self.tableView.setItem(item.row(), item.column(), newItem)

    def replaceText(self):
        mytext = self.findfield.text()
        newtext = self.replacefield.text()
        items = self.tableView.findItems(mytext, Qt.MatchContains)
        if items:
            item = items[0]
            row = item.row()
            column = item.column()
            val = item.text()
            newItem = QTableWidgetItem(val.replace(mytext, newtext))
            self.tableView.setItem(row, column, newItem)

    def replaceTextAll(self):
        mytext = self.findfield.text()
        newtext = self.replacefield.text()
        items = self.tableView.findItems(mytext, Qt.MatchContains)
        if items:
            for item in items:
                row = item.row()
                column = item.column()
                val = item.text()
                newItem = QTableWidgetItem(val.replace(mytext, newtext))
                self.tableView.setItem(row, column, newItem)
        self.isChanged = True

    def deleteRowByContext(self, event):
        row = self.selectedRow()
        self.tableView.removeRow(row)
        self.msg("Row " + str(row) + " deleted")
        self.tableView.selectRow(row)
        self.isChanged = True

    def addRowByContext(self, event):
        if self.tableView.columnCount() == 0:
            self.tableView.setColumnCount(1)
        if self.tableView.rowCount() == 0:
            self.tableView.setRowCount(1)
            self.tableView.selectRow(0)
        else:
            row = self.selectedRow()
            self.tableView.insertRow(row + 1)
            self.msg("Row at " + str(row) + " inserted")
            self.tableView.selectRow(row + 1)
        self.isChanged = True

    def addRowByContext2(self, event):
        if self.tableView.columnCount() == 0:
            self.tableView.setColumnCount(1)
        if self.tableView.rowCount() == 0:
            self.tableView.setRowCount(1)
            self.tableView.selectRow(0)
        else:
            row = self.selectedRow()
            self.tableView.insertRow(row)
            self.msg("Row at " + str(row) + " inserted")
            self.tableView.selectRow(row)
        self.isChanged = True

    def addColumnBeforeByContext(self, event):
        if self.tableView.columnCount() == 0:
            self.tableView.setColumnCount(1)
        else:
            col = self.selectedColumn()
            self.tableView.insertColumn(col)
            self.msg("Column at " + str(col) + " inserted")
        if self.tableView.rowCount() == 0:
            self.tableView.setRowCount(1)
        self.isChanged = True

    def addColumnAfterByContext(self, event):
        if self.tableView.columnCount() == 0:
            self.tableView.setColumnCount(1)
        else:
            col = self.selectedColumn() + 1
            self.tableView.insertColumn(col)
            self.msg("Column at " + str(col) + " inserted")
        if self.tableView.rowCount() == 0:
            self.tableView.setRowCount(1)
        self.isChanged = True

    def deleteColumnByContext(self, event):
        col = self.selectedColumn()
        self.tableView.removeColumn(col)
        self.msg("Column at " + str(col) + " removed")
        self.isChanged = True

    def copyByContext(self):
        row = self.selectedRow()
        col = self.selectedColumn()
        myitem = self.tableView.item(row, col)
        if myitem is not None:
            clip = QApplication.clipboard()
            clip.setText(myitem.text())

    def pasteByContext(self):
        row = self.selectedRow()
        col = self.selectedColumn()
        clip = QApplication.clipboard()
        newItem = QTableWidgetItem(clip.text())
        self.tableView.setItem(row, col, newItem)
        self.tableView.resizeColumnsToContents()
        self.isChanged = True

    def cutByContext(self):
        row = self.selectedRow()
        col = self.selectedColumn()
        myitem = self.tableView.item(row, col)
        if myitem is not None:
            clip = QApplication.clipboard()
            clip.setText(myitem.text())
            newItem = QTableWidgetItem("")
            self.tableView.setItem(row, col, newItem)
            self.isChanged = True

    def closeEvent(self, event):
        if self.isChanged == True:
            quit_msg = "<b>The document was changed.<br>Do you want to save the changes?</ b>"
            reply = QMessageBox.question(self, 'Save Confirmation',
                                         quit_msg, QMessageBox.Yes, QMessageBox.No)
            if reply == QMessageBox.Yes:
                event.accept()
                self.saveOnQuit()
        self.saveSettings()
        print("Goodbye ...")

    def readSettings(self):
        print("reading settings")
        if self.settings.contains("geometry"):
            self.setGeometry(self.settings.value('geometry'))
        if self.settings.contains("horHeader"):
            if self.settings.value('horHeader') == "true":
                self.tableView.horizontalHeader().setVisible(True)
            else:
                self.tableView.horizontalHeader().setVisible(False)
        if self.settings.contains("vertHeader"):
            if self.settings.value('vertHeader') == "true":
                self.tableView.verticalHeader().setVisible(True)
            else:
                self.tableView.verticalHeader().setVisible(False)

    def saveSettings(self):
        print("saving settings")
        self.settings.setValue('geometry', self.geometry())
        self.settings.setValue('horHeader', self.tableView.horizontalHeader().isVisible())
        self.settings.setValue('vertHeader', self.tableView.verticalHeader().isVisible())

    def saveOnQuit(self):
        if self.hasHeaders:
            self.setHeadersToFirstRow()
        if self.fileName == "":
            self.writeCsv()
        else:
            path = self.fileName
            with open(path, 'w') as stream:
                print("saving", path)
                writer = csv.writer(stream, delimiter=self.delimit)
                for row in range(self.tableView.rowCount()):
                    rowdata = []
                    for column in range(self.tableView.columnCount()):
                        item = self.tableView.item(row, column)
                        if item is not None:
                            rowdata.append(item.text())
                        else:
                            rowdata.append('')
                    writer.writerow(rowdata)
        self.setHeaders()
        self.isChanged = False

    def setCurrentFile(self, fileName):
        self.fileName = fileName
        self.fname = os.path.splitext(str(fileName))[0].split("/")[-1]
        if self.fileName:
            self.setWindowTitle(self.strippedName(self.fileName) + "[*]")
        else:
            self.setWindowTitle("no File")

        files = self.settings.value('recentFileList', [])

        try:
            files.remove(fileName)
        except ValueError:
            pass

        files.insert(0, fileName)
        del files[self.MaxRecentFiles:]

        self.settings.setValue('recentFileList', files)

        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, MyWindow):
                widget.updateRecentFileActions()

    def updateRecentFileActions(self):
        mytext = ""
        files = self.settings.value('recentFileList', [])
        numRecentFiles = min(len(files), self.MaxRecentFiles)

        for i in range(numRecentFiles):
            text = "&%d %s" % (i + 1, self.strippedName(files[i]))
            self.recentFileActs[i].setText(text)
            self.recentFileActs[i].setData(files[i])
            self.recentFileActs[i].setVisible(True)
            self.recentFileActs[i].setIcon(QIcon.fromTheme("gnome-mime-text-x"))

        for j in range(numRecentFiles, self.MaxRecentFiles):
            self.recentFileActs[j].setVisible(False)

        self.separatorAct.setVisible((numRecentFiles > 0))

    def clearRecentFiles(self, fileName):
        #        self.settings.clear()
        mf = []
        self.settings.setValue('recentFileList', mf)
        self.updateRecentFileActions()

    def strippedName(self, fullFileName):
        return QFileInfo(fullFileName).fileName()

    def msg(self, message):
        self.statusBar().showMessage(message)

    def setHeaders(self):
        self.tableView.selectRow(0)
        self.copyRow()
        for column in range(self.tableView.columnCount()):
            newItem = QTableWidgetItem(self.copiedRow[column])
            self.tableView.setHorizontalHeaderItem(column, newItem)
        self.tableView.removeRow(0)
        self.tableView.resizeColumnsToContents()
        self.hasHeaders = True

    def setHeadersToFirstRow(self):
        self.tableView.insertRow(0)
        for column in range(self.tableView.columnCount()):
            newItem = QTableWidgetItem(self.tableView.horizontalHeaderItem(column))
            ind = QTableWidgetItem(str(column + 1))
            self.tableView.setHorizontalHeaderItem(column, ind)
            self.tableView.setItem(0, column, newItem)
        self.hasHeaders = False

    def copyRow(self):
        row = self.selectedRow()
        for column in range(self.tableView.columnCount()):
            if not self.tableView.item(row, column) == None:
                self.copiedRow.append(self.tableView.item(row, column).text())

    def pasteRow(self):
        row = self.selectedRow()
        for column in range(self.tableView.columnCount()):
            newItem = QTableWidgetItem(self.copiedRow[column])
            self.tableView.setItem(row, column, newItem)

    def copyColumn(self):
        column = self.selectedColumn()
        for row in range(self.tableView.rowCount()):
            self.copiedColumn.append(self.tableView.item(row, column).text())

    def pasteColumn(self):
        column = self.selectedColumn()
        for row in range(self.tableView.rowCount()):
            newItem = QTableWidgetItem(self.copiedColumn[row])
            self.tableView.setItem(row, column, newItem)
            self.tableView.resizeColumnsToContents()


def stylesheet(self):
    return """
 QTableWidget
{
background: #e1e1e1;
selection-color: white;
border: 1px solid lightgrey;
selection-background-color: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #729fcf, stop: 1  #204a87);
color: #202020;
outline: 0;
} 
QTableWidget::item::hover{
background: qlineargradient(y1: 0, y2: 1, stop: 0 #babdb6, stop: 0.5 #d3d7cf, stop: 1 #babdb6);
}
QTableWidget::item::focus
{
background: qlineargradient( y1: 0, y2: 1, stop: 0 #729fcf, stop: 1  #204a87);
border: 0px;
}
QHeaderView::section
{background-color:#d3d7cf;
color: #2e3436; 
font: bold
}
QTableCornerButton::section 
{
background-color:#d3d7cf; 
}
QStatusBar
{
    font-size: 7pt;
    color: #717171
}
QLineEdit
{
   color: #484848;
    background-color: #fbfbfb;
}
QMenuBar
{
background: transparent;
border: 0px;
}
QToolBar
{
background: transparent;
border: 0px;
}
QPushButton
{
background: #d3d7cf ;
}
QMainWindow
{
     background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                 stop: 0 #E1E1E1, stop: 0.4 #DDDDDD,
                                 stop: 0.5 #D8D8D8, stop: 1.0 #D3D3D3);
}
QLineEdit
{
     background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                 stop: 0 #E1E1E1, stop: 0.4 #e5e5e5,
                                 stop: 0.5 #e9e9e9, stop: 1.0 #d2d2d2);
}
    """


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    app.setApplicationName('MyWindow')
    main = MyWindow('')
    main.setMinimumSize(820, 300)
    main.setWindowTitle("CSV Viewer")
    main.show()

sys.exit(app.exec_())