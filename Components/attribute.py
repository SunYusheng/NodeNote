import re
import os
import io
import time
from collections import OrderedDict
import validators
import matplotlib.pyplot as plt
import pylab
import numpy as np
from PyQt5 import QtCore, QtWidgets, QtGui
from Model import constants, stylesheet, serializable
from Components import port, pipe

__all__ = ["SubConstituteWidget", "InputTextField",
           "LogicWidget", "TruthWidget", "AttributeWidget", "AttributeFile"]


class SizeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(SizeDialog, self).__init__(parent)
        self.resize(100, 80)
        self.setWindowTitle("Set Image Width and Height")
        self.setWindowIcon(QtGui.QIcon("Resources/Dialog_icon/Plane.png"))

        self.num_width = QtWidgets.QLineEdit(parent=self)
        self.num_width.setValidator(QtGui.QDoubleValidator())
        self.num_height = QtWidgets.QLineEdit(parent=self)
        self.num_height.setValidator(QtGui.QDoubleValidator())
        grid = QtWidgets.QGridLayout()
        grid.addWidget(QtWidgets.QLabel("Width: ", parent=self), 0, 0, 1, 1)
        grid.addWidget(QtWidgets.QLabel("Height: ", parent=self), 1, 0, 1, 1)
        grid.addWidget(self.num_width, 0, 1, 1, 1)
        grid.addWidget(self.num_height, 1, 1, 1, 1)

        button_box = QtWidgets.QDialogButtonBox(parent=self)
        button_box.setOrientation(QtCore.Qt.Horizontal)
        button_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel |
                                      QtWidgets.QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(grid)
        spacerItem = QtWidgets.QSpacerItem(20, 48, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        layout.addItem(spacerItem)
        layout.addWidget(button_box)
        self.setLayout(layout)

    def closeEvent(self, event):
        reply = QtWidgets.QMessageBox.question(self, 'Close Message',
                                               "Are you sure to quit?", QtWidgets.QMessageBox.Yes |
                                               QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()


def format(color, style=''):
    """Return a QTextCharFormat with the given attributes.
    """
    _color = QtGui.QColor()
    _color.setNamedColor(color)

    _format = QtGui.QTextCharFormat()
    _format.setForeground(_color)
    if 'bold' in style:
        _format.setFontWeight(QtGui.QFont.Bold)
    if 'italic' in style:
        _format.setFontItalic(True)

    return _format


# Syntax styles that can be shared by all languages
STYLES = {
    'keyword': format('blue'),
    'operator': format('red'),
    'brace': format('darkGray'),
    'defclass': format('black', 'bold'),
    'string': format('magenta'),
    'string2': format('darkMagenta'),
    'comment': format('darkGreen', 'italic'),
    'self': format('black', 'italic'),
    'numbers': format('brown'),
}


class PythonHighlighter(QtGui.QSyntaxHighlighter):
    """Syntax highlighter for the Python language.
    """
    # Python keywords
    keywords = [
        'and', 'assert', 'break', 'class', 'continue', 'def',
        'del', 'elif', 'else', 'except', 'exec', 'finally',
        'for', 'from', 'global', 'if', 'import', 'in',
        'is', 'lambda', 'not', 'or', 'pass', 'print',
        'raise', 'return', 'try', 'while', 'yield',
        'None', 'True', 'False',
    ]

    # Python operators
    operators = [
        '=',
        # Comparison
        '==', '!=', '<', '<=', '>', '>=',
        # Arithmetic
        '\+', '-', '\*', '/', '//', '\%', '\*\*',
        # In-place
        '\+=', '-=', '\*=', '/=', '\%=',
        # Bitwise
        '\^', '\|', '\&', '\~', '>>', '<<',
    ]

    # Python braces
    braces = [
        '\{', '\}', '\(', '\)', '\[', '\]',
    ]

    def __init__(self, document):
        QtGui.QSyntaxHighlighter.__init__(self, document)

        self.tri_single = (QtCore.QRegExp("'''"), 1, STYLES['string2'])
        self.tri_double = (QtCore.QRegExp('"""'), 2, STYLES['string2'])

        rules = []

        # Keyword, operator, and brace rules
        rules += [(r'\b%s\b' % w, 0, STYLES['keyword'])
                  for w in PythonHighlighter.keywords]
        rules += [(r'%s' % o, 0, STYLES['operator'])
                  for o in PythonHighlighter.operators]
        rules += [(r'%s' % b, 0, STYLES['brace'])
                  for b in PythonHighlighter.braces]

        # All other rules
        rules += [
            # 'self'
            (r'\bself\b', 0, STYLES['self']),

            # Double-quoted string, possibly containing escape sequences
            (r'"[^"\\]*(\\.[^"\\]*)*"', 0, STYLES['string']),
            # Single-quoted string, possibly containing escape sequences
            (r"'[^'\\]*(\\.[^'\\]*)*'", 0, STYLES['string']),

            # 'def' followed by an identifier
            (r'\bdef\b\s*(\w+)', 1, STYLES['defclass']),
            # 'class' followed by an identifier
            (r'\bclass\b\s*(\w+)', 1, STYLES['defclass']),

            # From '#' until a newline
            (r'#[^\n]*', 0, STYLES['comment']),

            # Numeric literals
            (r'\b[+-]?[0-9]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?0[xX][0-9A-Fa-f]+[lL]?\b', 0, STYLES['numbers']),
            (r'\b[+-]?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\b', 0, STYLES['numbers']),
        ]

        # Build a QRegExp for each pattern
        self.rules = [(QtCore.QRegExp(pat), index, fmt)
                      for (pat, index, fmt) in rules]

    def highlightBlock(self, text):
        """Apply syntax highlighting to the given block of text.
        """
        # Do other syntax formatting
        for expression, nth, font_format in self.rules:
            index = expression.indexIn(text, 0)

            while index >= 0:
                # We actually want the index of the nth match
                index = expression.pos(nth)
                length = len(expression.cap(nth))
                self.setFormat(index, length, font_format)
                index = expression.indexIn(text, index + length)

        self.setCurrentBlockState(0)

        # Do multi-line strings
        in_multiline = self.match_multiline(text, *self.tri_single)
        if not in_multiline:
            self.match_multiline(text, *self.tri_double)

    def match_multiline(self, text, delimiter, in_state, style):
        """Do highlighting of multi-line strings. ``delimiter`` should be a
        ``QRegExp`` for triple-single-quotes or triple-double-quotes, and
        ``in_state`` should be a unique integer to represent the corresponding
        state changes when inside those strings. Returns True if we're still
        inside a multi-line string when this function is finished.
        """
        # If inside triple-single quotes, start at 0
        if self.previousBlockState() == in_state:
            start = 0
            add = 0
        # Otherwise, look for the delimiter on this line
        else:
            start = delimiter.indexIn(text)
            # Move past this match
            add = delimiter.matchedLength()

        # As long as there's a delimiter match on this line...
        while start >= 0:
            # Look for the ending delimiter
            end = delimiter.indexIn(text, start + add)
            # Ending delimiter on this line?
            if end >= add:
                length = end - start + add + delimiter.matchedLength()
                self.setCurrentBlockState(0)
            # No; multi-line string
            else:
                self.setCurrentBlockState(in_state)
                length = len(text) - start + add
            # Apply formatting
            self.setFormat(start, length, style)
            # Look for the next match
            start = delimiter.indexIn(text, start + length)

        # Return True if still inside a multi-line string, False otherwise
        if self.currentBlockState() == in_state:
            return True
        else:
            return False


class SimpleTextField(QtWidgets.QGraphicsTextItem):
    def __init__(self, text, parent):
        super(SimpleTextField, self).__init__(text, parent)
        self.setFlags(QtWidgets.QGraphicsWidget.ItemSendsGeometryChanges | QtWidgets.QGraphicsWidget.ItemIsSelectable)
        self.document().contentsChanged.connect(self.control_length)

    def mouseDoubleClickEvent(self, event) -> None:
        super(SimpleTextField, self).mouseDoubleClickEvent(event)
        self.setFlag(QtWidgets.QGraphicsWidget.ItemIsFocusable, True)
        self.setFocus()

    def focusInEvent(self, event) -> None:
        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        super(SimpleTextField, self).focusInEvent(event)

    def focusOutEvent(self, event: QtGui.QFocusEvent) -> None:
        self.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        super(SimpleTextField, self).focusOutEvent(event)

    def control_length(self):
        if len(self.document().toPlainText()) >= 18:
            self.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)


class InputTextField(QtWidgets.QGraphicsTextItem):
    edit_finished = QtCore.pyqtSignal(bool)
    start_editing = QtCore.pyqtSignal()

    def __init__(self, text, node, parent=None, single_line=False):
        super(InputTextField, self).__init__(text, parent)
        # BASIC SETTINGS
        self.setFlags(QtWidgets.QGraphicsWidget.ItemSendsGeometryChanges | QtWidgets.QGraphicsWidget.ItemIsSelectable)
        self.setOpenExternalLinks(True)
        self.setObjectName("Nothing")
        self.node = node
        self.single_line = single_line
        self.text_before_editing = ""
        self.origMoveEvent = self.mouseMoveEvent
        self.mouseMoveEvent = self.node.mouseMoveEvent
        # DOCUMNET SETTINGS
        self.document().setIndentWidth(4)
        self.document().setDefaultFont(QtGui.QFont("Inconsolata", 8))
        self.pythonlighter = PythonHighlighter(self.document())
        self.editing_state = False
        self.font_size_editing = True

    @staticmethod
    def add_table(cursor):
        # create parameters
        table_format = QtGui.QTextTableFormat()

        # set and insert
        table_format.setCellPadding(10)
        table_format.setCellSpacing(2)
        table_format.setAlignment(QtCore.Qt.AlignCenter)
        table_format.setBackground(QtGui.QBrush(QtGui.QColor(229, 255, 255, 255)))
        cursor.insertTable(1, 1, table_format)

    @staticmethod
    def table_insert_column(table, cursor):
        column = table.cellAt(cursor).column() + 1
        table.insertColumns(column, 1)

    @staticmethod
    def table_insert_row(table, cursor):
        row = table.cellAt(cursor).row() + 1
        table.insertRows(row, 1)

    @staticmethod
    def table_delete_column(table, cursor):
        column = table.cellAt(cursor).column()
        table.removeColumns(column, 1)

    @staticmethod
    def table_delete_row(table, cursor):
        row = table.cellAt(cursor).row()
        table.removeRows(row, 1)

    @staticmethod
    def add_list(cursor):
        # create parameters
        list_format = QtGui.QTextListFormat()

        # set and insert
        list_format.setIndent(4)
        list_format.setStyle(QtGui.QTextListFormat.ListDecimal)
        cursor.insertList(list_format)

    def indent(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            temp = cursor.blockNumber()
            cursor.setPosition(cursor.anchor())
            diff = cursor.blockNumber() - temp
            direction = QtGui.QTextCursor.Up if diff > 0 else QtGui.QTextCursor.Down
            for _ in range(abs(diff) + 1):
                cursor.movePosition(QtGui.QTextCursor.StartOfLine)
                cursor.insertText("    ")
                cursor.movePosition(direction)
        else:
            cursor.insertText("    ")

    def dedent(self):
        cursor = self.textCursor()
        if cursor.hasSelection():
            temp = cursor.blockNumber()
            cursor.setPosition(cursor.anchor())
            diff = cursor.blockNumber() - temp
            direction = QtGui.QTextCursor.Up if diff > 0 else QtGui.QTextCursor.Down
            for _ in range(abs(diff) + 1):
                cursor.movePosition(QtGui.QTextCursor.StartOfLine)
                line = cursor.block().text()
                if line.startswith("    "):
                    for _ in range(4):
                        cursor.deleteChar()
                else:
                    for char in line[:4]:
                        if char != " ":
                            break
                        cursor.deleteChar()
                cursor.movePosition(direction)
        else:
            cursor.movePosition(QtGui.QTextCursor.StartOfLine)
            line = cursor.block().text()
            if line.startswith("    "):
                for _ in range(4):
                    cursor.deleteChar()
            else:
                for char in line[:4]:
                    if char != " ":
                        break
                    cursor.deleteChar()

    def get_text_maxlength(self):
        document = self.document()
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.Start)
        root = document.rootFrame()
        it = root.begin()
        maxlength = 0
        while it != root.end():
            line_length = self.get_line_length(cursor)
            maxlength = maxlength if maxlength > line_length else line_length
            cursor.movePosition(QtGui.QTextCursor.Down)
            it += 1
        return maxlength

    @staticmethod
    def get_line_length(cursor):
        if constants.DEBUG_RICHTEXT:
            print("cursor postion: ", cursor.position())
        line_type = list()
        for char in cursor.block().text():
            if '\u4e00' <= char <= '\u9fa5':
                line_type.append(1)
                if constants.DEBUG_RICHTEXT:
                    print("Chinese: ", char)
            else:
                line_type.append(0)

        line_position = 0
        line_point = 0
        cursor.movePosition(QtGui.QTextCursor.StartOfLine)
        while not cursor.atBlockEnd():
            point_size = cursor.charFormat().fontPointSize()
            font_point_size = point_size if point_size != 0 else 8
            if line_type[line_position]:
                font_point_size = font_point_size * 2
            line_point += font_point_size
            line_position += 1
            cursor.movePosition(QtGui.QTextCursor.Right, QtGui.QTextCursor.KeepAnchor, 1)
        return line_point

    def align(self, align):
        max_length = self.get_text_maxlength()
        cursor = self.textCursor()
        if align == "Center":
            self.align("Clean")
            if cursor.hasSelection():
                temp = cursor.blockNumber()
                cursor.setPosition(cursor.anchor())
                diff = cursor.blockNumber() - temp
                direction = QtGui.QTextCursor.Up if diff > 0 else QtGui.QTextCursor.Down
                for _ in range(abs(diff) + 1):
                    line_length = self.get_line_length(cursor)
                    blank_number = int(((max_length - line_length) // 2) // 8)
                    if constants.DEBUG_RICHTEXT:
                        print("max length, line length, blank number", max_length, line_length, blank_number)
                    cursor.movePosition(QtGui.QTextCursor.StartOfLine)
                    cursor.insertText(" " * blank_number)
                    cursor.movePosition(QtGui.QTextCursor.EndOfLine)
                    cursor.insertText(" " * blank_number)
                    cursor.movePosition(direction)
                    self.setTextCursor(cursor)
            else:
                line_length = self.get_line_length(cursor)
                blank_number = int(((max_length - line_length) // 2) // 8)
                if constants.DEBUG_RICHTEXT:
                    print("max length, line length, blank number", max_length, line_length, blank_number)
                cursor.movePosition(QtGui.QTextCursor.StartOfLine)
                cursor.insertText(" " * blank_number)
                cursor.movePosition(QtGui.QTextCursor.EndOfLine)
                cursor.insertText(" " * blank_number)
                self.setTextCursor(cursor)
        elif align == "Left":
            self.align("Clean")
            if cursor.hasSelection():
                temp = cursor.blockNumber()
                cursor.setPosition(cursor.anchor())
                diff = cursor.blockNumber() - temp
                direction = QtGui.QTextCursor.Up if diff > 0 else QtGui.QTextCursor.Down
                for _ in range(abs(diff) + 1):
                    cursor.movePosition(QtGui.QTextCursor.StartOfLine)
                    line = cursor.block().text()
                    for char in line[:]:
                        if char != " ":
                            break
                        cursor.deleteChar()
                    cursor.movePosition(direction)
                    self.setTextCursor(cursor)
            else:
                cursor.movePosition(QtGui.QTextCursor.StartOfLine)
                line = cursor.block().text()
                for char in line:
                    if char != " ":
                        break
                    cursor.deleteChar()
                self.setTextCursor(cursor)
        elif align == "Right":
            self.align("Clean")
            if cursor.hasSelection():
                temp = cursor.blockNumber()
                cursor.setPosition(cursor.anchor())
                diff = cursor.blockNumber() - temp
                direction = QtGui.QTextCursor.Up if diff > 0 else QtGui.QTextCursor.Down
                for _ in range(abs(diff) + 1):
                    line_length = self.get_line_length(cursor)
                    blank_number = int((max_length - line_length) // 8)
                    cursor.movePosition(QtGui.QTextCursor.StartOfLine)
                    for _ in range(blank_number):
                        cursor.insertText(" ")
                    cursor.movePosition(direction)
                    self.setTextCursor(cursor)
            else:
                line_length = self.get_line_length(cursor)
                blank_number = int((max_length - line_length) // 8)
                cursor.movePosition(QtGui.QTextCursor.StartOfLine)
                for _ in range(blank_number):
                    cursor.insertText(" ")
                self.setTextCursor(cursor)
        elif align == "Clean":
            if cursor.hasSelection():
                temp = cursor.blockNumber()
                cursor.setPosition(cursor.anchor())
                diff = cursor.blockNumber() - temp
                direction = QtGui.QTextCursor.Up if diff > 0 else QtGui.QTextCursor.Down
                for _ in range(abs(diff) + 1):
                    cursor.movePosition(QtGui.QTextCursor.StartOfLine)
                    line = cursor.block().text()
                    for char in line:
                        if char != " ":
                            break
                        cursor.deleteChar()
                        if constants.DEBUG_RICHTEXT:
                            print("line: ", cursor.block().text(), len(cursor.block().text()))
                    index = len(line.strip())
                    if constants.DEBUG_RICHTEXT:
                        print("Before move: ", cursor.position(), index)
                    cursor.movePosition(QtGui.QTextCursor.Right, QtGui.QTextCursor.MoveAnchor, index)
                    if constants.DEBUG_RICHTEXT:
                        print("After move: ", cursor.position(), index, line.lstrip()[index:])
                    for char in line.lstrip()[index:]:
                        if char != " ":
                            break
                        cursor.deleteChar()
                        if constants.DEBUG_RICHTEXT:
                            print("line: ", cursor.block().text(), len(cursor.block().text()))
                    cursor.movePosition(direction)
                    self.setTextCursor(cursor)
            else:
                cursor.movePosition(QtGui.QTextCursor.StartOfLine)
                line = cursor.block().text()
                for char in line:
                    if char != " ":
                        break
                    cursor.deleteChar()
                    if constants.DEBUG_RICHTEXT:
                        print("line: ", cursor.block().text(), len(cursor.block().text()))
                index = len(line.strip())
                if constants.DEBUG_RICHTEXT:
                    print("Before move: ", cursor.position(), index)
                cursor.movePosition(QtGui.QTextCursor.Right, QtGui.QTextCursor.MoveAnchor, index)
                if constants.DEBUG_RICHTEXT:
                    print("After move: ", cursor.position(), index, line.lstrip()[index:])
                for char in line.lstrip()[index:]:
                    if char != " ":
                        break
                    cursor.deleteChar()
                    if constants.DEBUG_RICHTEXT:
                        print("line: ", cursor.block().text(), len(cursor.block().text()))
                self.setTextCursor(cursor)

    @staticmethod
    def latex_formula(str_latex):
        font_size = 8
        dpi = 300
        fig = pylab.figure()
        text = fig.text(0, 0, str_latex, fontsize=font_size)

        buff = io.BytesIO()
        fig.savefig(buff, format="png", dpi=dpi)
        bbox = text.get_window_extent()
        width, height = bbox.size / float(dpi) + 0.005
        fig.set_size_inches((width, height))
        dy = (bbox.ymin / float(dpi)) / height
        text.set_position((0, -dy))
        buff = io.BytesIO()
        fig.savefig(buff, format="png", dpi=dpi)

        buff.seek(0)
        img = plt.imread(buff)
        im = img.mean(axis=2)
        im = ((im - im.min()) / (im.ptp() / 255.0)).astype(np.uint8)
        temp_img = QtGui.QImage(im, im.shape[1], im.shape[0], im.shape[1], QtGui.QImage.Format_Indexed8)
        image = QtGui.QPixmap(temp_img).toImage()
        size = image.size()
        image = image.scaled(size.width() * 0.5, size.height() * 0.5,
                             QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
        return image

    def font_format(self, font_type):
        cursor = self.textCursor()
        text_format = QtGui.QTextCharFormat()
        if font_type == "Italic":
            if cursor.charFormat().fontItalic():
                text_format.setFontItalic(False)
            else:
                text_format.setFontItalic(True)
            cursor.mergeCharFormat(text_format)
            self.editing_state = False
        elif font_type == "Blod":
            if cursor.charFormat().fontWeight() == 50:
                text_format.setFontWeight(100)
            else:
                text_format.setFontWeight(50)
            cursor.mergeCharFormat(text_format)
            self.editing_state = False
        elif font_type == "Underline":
            if cursor.charFormat().fontUnderline():
                text_format.setFontUnderline(False)
            else:
                text_format.setFontUnderline(True)
                text_format.setUnderlineColor(QtGui.QColor(133, 255, 255))
            cursor.mergeCharFormat(text_format)
            self.editing_state = False
        elif font_type == "Deleteline":
            if cursor.charFormat().fontStrikeOut():
                text_format.setFontStrikeOut(False)
            else:
                text_format.setFontStrikeOut(True)
            cursor.mergeCharFormat(text_format)
            self.editing_state = False
        elif font_type == "Up":
            if constants.DEBUG_RICHTEXT:
                print("Font size: ", cursor.charFormat().fontPointSize())
            if cursor.charFormat().fontPointSize() == 0:
                font_point_size = 8
            else:
                font_point_size = cursor.charFormat().fontPointSize()
            point_size = font_point_size + 2
            text_format.setFontPointSize(point_size)
            cursor.mergeCharFormat(text_format)
            self.editing_state = True
            self.font_size_editing = True
        elif font_type == "Down":
            if constants.DEBUG_RICHTEXT:
                print("Font size: ", cursor.charFormat().fontPointSize())
            if cursor.charFormat().fontPointSize() == 0:
                font_point_size = 8
            else:
                font_point_size = cursor.charFormat().fontPointSize()
            point_size = font_point_size - 2 if font_point_size - 2 > 0 else 2
            text_format.setFontPointSize(point_size)
            cursor.mergeCharFormat(text_format)
            self.editing_state = True
            self.font_size_editing = True
        elif font_type == "Color":
            color = QtWidgets.QColorDialog.getColor(QtCore.Qt.red, None, "Select Color",
                                                    QtWidgets.QColorDialog.ShowAlphaChannel)
            if color:
                text_format.setForeground(color)
            cursor.mergeCharFormat(text_format)
            self.editing_state = False
        elif font_type == "Hyperlink":
            if not cursor.charFormat().isAnchor():
                text_format.setAnchor(True)
                text_format.setForeground(QtGui.QColor("Blue"))
                text_format.setAnchorHref(cursor.selection().toPlainText())
            else:
                text_format.setAnchor(False)
                text_format.setForeground(QtGui.QColor("Black"))
            cursor.mergeCharFormat(text_format)
            self.editing_state = False
        elif font_type == "Mathjax":
            str_latex = cursor.selection().toPlainText()
            if str_latex.startswith("$") and str_latex.endswith("$") and str_latex.count("$") == 2:
                image = self.latex_formula(str_latex)
                image_folder = os.getcwd() + "//Assets//"
                if not os.path.exists(image_folder):
                    os.makedirs(image_folder)
                image_name = "%s/%s.png" % (image_folder, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime()))
                image.save(image_name, quality=50)
                cursor.clearSelection()
                cursor.insertText("\n")
                cursor.insertImage(image_name)
                self.editing_state = False
        elif font_type == "Clear":
            cursor.setCharFormat(text_format)
            self.editing_state = False
        if not self.editing_state:
            cursor.movePosition(QtGui.QTextCursor.EndOfBlock)
            cursor.setCharFormat(QtGui.QTextCharFormat())
            self.setTextCursor(cursor)

    def image_format(self):
        cursor = self.textCursor()
        image_width = self.get_text_maxlength()
        image_height = 50
        if cursor.hasSelection():
            size_dialog = SizeDialog()
            text = cursor.selection().toHtml(bytes())
            if text.find(r'<img src=') != -1:
                cursor.removeSelectedText()
                if size_dialog.exec_():
                    image_width = size_dialog.num_width.text() if size_dialog.num_width.text() else image_width
                    image_height = size_dialog.num_height.text() if size_dialog.num_height.text() else image_height
                if constants.DEBUG_RICHTEXT:
                    print("image size: ", image_width, image_height)
                pattern = re.compile(r'<img src="(.+?)".+?/>')
                text = pattern.sub(r'<img src="\1" width="%s" height="%s" />' % (image_width, image_height), text)
                if constants.DEBUG_RICHTEXT:
                    print("*****************text***********************\n", text, "\n** \
                                                                                  ************************************")
                cursor.insertHtml(text)
            else:
                cursor.clearSelection()
                self.setTextCursor(cursor)

    def copy(self):
        text_cursor = self.textCursor()
        clipboard = QtWidgets.QApplication.clipboard()
        if text_cursor.hasSelection():
            mime_data = QtCore.QMimeData()
            html_data = text_cursor.selection().toHtml(bytes())
            mime_data.setHtml(html_data)
            clipboard.setMimeData(mime_data)

    @staticmethod
    def paste(cursor):
        mime_data = QtWidgets.QApplication.clipboard().mimeData()
        if mime_data.hasHtml():
            cursor.insertHtml(mime_data.html())
        if mime_data.hasImage():
            image = QtGui.QImage(mime_data.imageData())
            image_folder = os.getcwd() + "/Assets"
            if not os.path.exists(image_folder):
                os.makedirs(image_folder)
            image_name = "%s/%s.png" % (image_folder, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime()))
            image.save(image_name, quality=50)
            image_format = QtGui.QTextImageFormat()
            image_format.setName(image_name)
            cursor.insertImage(image_format)
        elif mime_data.hasUrls():
            for u in mime_data.urls():
                file_ext = os.path.splitext(str(u.toLocalFile()))[1].lower()
                if constants.DEBUG_RICHTEXT:
                    print(file_ext, u.isLocalFile())
                if u.isLocalFile() and file_ext in ('.jpg', '.png', '.bmp', '.icon', '.jpeg', 'gif'):
                    image = QtGui.QImage(u.toLocalFile())
                    url = u.url()
                    first_index = url.rindex('/')
                    second_index = url[:first_index].rindex('/')
                    if url[second_index + 1: first_index] != "Assets":
                        image_folder = os.getcwd() + "//Assets//"
                        if not os.path.exists(image_folder):
                            os.makedirs(image_folder)
                        image_name = "%s/%s.png" % (image_folder, time.strftime("%Y-%m-%d-%H:%M:%S", time.localtime()))
                        image.save(image_name, quality=50)
                    cursor.insertImage(image)
                else:
                    break
            else:
                return
        elif mime_data.hasText():
            text = mime_data.text()
            cursor.insertText(text)
            if constants.DEBUG_RICHTEXT:
                print("PASTE: ", text)

    def keyPressEvent(self, event) -> None:
        # insert key text into text field.
        current_key = event.key()
        current_cursor = self.textCursor()

        # restore text before editing and return.
        if current_key == QtCore.Qt.Key_Escape:
            self.clearFocus()
            super(InputTextField, self).keyPressEvent(event)
            return
        elif current_key == QtCore.Qt.Key_BracketLeft and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("ALIGN LEFT")
            self.align("Left")
        elif current_key == QtCore.Qt.Key_BracketRight and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("ALIGN RIGHT")
            self.align("Right")
        elif current_key == QtCore.Qt.Key_Backslash and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("ALIGN CENTER")
            self.align("Center")
        elif current_key == QtCore.Qt.Key_P and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("ALIGN Clean")
            self.align("Clean")
        elif current_key == QtCore.Qt.Key_Q and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("Rich Format: Title")
            self.font_format("Italic")
        elif current_key == QtCore.Qt.Key_W and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("Rich Format: Title")
            self.font_format("Blod")
        elif current_key == QtCore.Qt.Key_R and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("Rich Format: Title")
            self.font_format("Underline")
        elif current_key == QtCore.Qt.Key_F and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("Rich Format: Title")
            self.font_format("Deleteline")
        elif current_key == QtCore.Qt.Key_G and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("Rich Format: Title")
            self.font_format("Up")
        elif current_key == QtCore.Qt.Key_H and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("Rich Format: Title")
            self.font_format("Down")
        elif current_key == QtCore.Qt.Key_N and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("Rich Format: Title")
            self.font_format("Color")
        elif current_key == QtCore.Qt.Key_M and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("Rich Format: Title")
            self.font_format("Hyperlink")
        elif current_key == QtCore.Qt.Key_Y and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("Rich Format: Title")
            self.font_format("Mathjax")
        elif current_key == QtCore.Qt.Key_L and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("Rich Format: Title")
            self.font_format("Clear")

        if self.single_line:
            if current_key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                if self.toPlainText() == "":
                    self.setHtml(self.text_before_editing)
                    event.ignore()
                    self.edit_finished.emit(False)
                    self.clearFocus()
                else:
                    event.ignore()
                    self.clearFocus()
            else:
                super(InputTextField, self).keyPressEvent(event)
        else:
            super(InputTextField, self).keyPressEvent(event)

        # table operation
        current_table = current_cursor.currentTable()
        if current_key == QtCore.Qt.Key_1 and event.modifiers() & QtCore.Qt.ControlModifier:
            self.add_table(current_cursor)
        if current_key == QtCore.Qt.Key_T and event.modifiers() & QtCore.Qt.ControlModifier and current_table:
            self.table_insert_column(current_table, current_cursor)
        if current_key == QtCore.Qt.Key_R and event.modifiers() & QtCore.Qt.ControlModifier and current_table:
            self.table_insert_row(current_table, current_cursor)
        if current_key == QtCore.Qt.Key_D and event.modifiers() & QtCore.Qt.ControlModifier and current_table:
            self.table_delete_column(current_table, current_cursor)
        if current_key == QtCore.Qt.Key_M and event.modifiers() & QtCore.Qt.ControlModifier and current_table:
            self.table_delete_row(current_table, current_cursor)

        # list operation
        if current_key == QtCore.Qt.Key_2 and event.modifiers() & QtCore.Qt.ControlModifier:
            self.add_list(current_cursor)

        # image
        if current_key == QtCore.Qt.Key_U and event.modifiers() & QtCore.Qt.ControlModifier:
            if constants.DEBUG_RICHTEXT:
                print("Rich Format: Image")
            self.image_format()

    def sceneEvent(self, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.KeyPress:
            if event.matches(QtGui.QKeySequence.Paste):
                self.paste(self.textCursor())
                return False
            elif event.matches(QtGui.QKeySequence.Copy):
                self.copy()
                return False
            elif event.key() == QtCore.Qt.Key_Tab:
                if event.modifiers() == QtCore.Qt.ControlModifier:
                    if constants.DEBUG_RICHTEXT:
                        print("CTRL + TAB")
                    self.dedent()
                    return False
                else:
                    if constants.DEBUG_RICHTEXT:
                        print("TAB")
                    self.indent()
                    return False
            else:
                super(InputTextField, self).sceneEvent(event)
                return False
        else:
            super(InputTextField, self).sceneEvent(event)
            return False

    def mousePressEvent(self, event) -> None:
        # change focus into node
        hyperlink = self.textCursor().charFormat().isAnchor()
        if hyperlink:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.PointingHandCursor)
        if self.objectName() == "MouseLocked":
            super(InputTextField, self).mousePressEvent(event)
        else:
            self.node.mousePressEvent(event)
            self.clearFocus()

    def contextMenuEvent(self, event: 'QtWidgets.QGraphicsSceneContextMenuEvent') -> None:
        # not implementing, debug for right mouse clicked
        pass

    def mouseReleaseEvent(self, event) -> None:
        # change focus into node
        hyperlink = self.textCursor().charFormat().isAnchor()
        if hyperlink:
            url = self.textCursor().charFormat().anchorHref()
            try:
                validators.url(url)
                QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
            except Exception as e:
                print("Valid hyperlink: ", e)
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.ArrowCursor)
        if self.objectName() == "MouseLocked":
            super(InputTextField, self).mouseReleaseEvent(event)
        else:
            self.node.mouseReleaseEvent(event)
            self.clearFocus()

    def mouseDoubleClickEvent(self, event) -> None:
        # get focus
        super(InputTextField, self).mouseDoubleClickEvent(event)
        self.setFlag(QtWidgets.QGraphicsWidget.ItemIsFocusable, True)
        self.start_editing.emit()
        self.setFocus()

    def focusInEvent(self, event) -> None:
        self.setTextInteractionFlags(QtCore.Qt.TextEditorInteraction)
        self.setObjectName("MouseLocked")
        self.text_before_editing = self.toHtml()
        self.mouseMoveEvent = self.origMoveEvent
        super(InputTextField, self).focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        super(InputTextField, self).focusOutEvent(event)
        self.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        self.setObjectName("Nothing")
        if constants.DEBUG_RICHTEXT:
            print("Html contents:\n", self.toHtml())
        if not self.editing_state or self.font_size_editing:
            cursor = self.textCursor()
            cursor.clearSelection()
            self.setTextCursor(cursor)
            self.font_size_editing = False
        self.mouseMoveEvent = self.node.mouseMoveEvent


class SubConstituteWidget(QtWidgets.QGraphicsWidget):
    def __init__(self, parent=None):
        super(SubConstituteWidget, self).__init__(parent)
        # SET BASIC FUNCTION
        self.hovered = False
        self.setAcceptHoverEvents(True)
        self.setFlag(QtWidgets.QGraphicsWidget.ItemSendsGeometryChanges)
        self.setCacheMode(QtWidgets.QGraphicsItem.DeviceCoordinateCache)

        # LABEL ITEM
        self.label_item = InputTextField(self.parentItem().name, parent, self,
                                         single_line=False)
        self.label_item.setAcceptHoverEvents(True)
        self.label_item.document().contentsChanged.connect(self.parentItem().text_change_node_shape)
        self.label_item.document().contentsChanged.connect(self.parentItem().update_treelist)
        self.label_item.hoverMoveEvent = self.hoverMoveEvent
        self.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Maximum)
        self.layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Horizontal)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.label_widget = QtWidgets.QGraphicsWidget()
        self.label_widget.setGraphicsItem(self.label_item)
        self.layout.addItem(self.label_widget)
        self.setLayout(self.layout)

    def hoverEnterEvent(self, event) -> None:
        super(SubConstituteWidget, self).hoverEnterEvent(event)
        self.hovered = True
        self.update()

    def hoverMoveEvent(self, event) -> None:
        self.parentItem().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event) -> None:
        super(SubConstituteWidget, self).hoverLeaveEvent(event)
        self.hovered = False
        self.update()

    def sizeHint(self, which=None, constraint=None) -> QtCore.QSizeF:
        width = self.label_item.boundingRect().width()
        height = self.label_item.boundingRect().height() + 5
        return QtCore.QSizeF(width, height)


class GroupWidget(QtWidgets.QGroupBox):
    def __init__(self, label, parent=None):
        super(GroupWidget, self).__init__(parent)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setSpacing(4)
        self.setTitle(label)

    def setTitle(self, text):
        margin = (0, 0, 0, 0)
        padding_top = '14px'
        if text == '':
            margin = (0, 2, 0, 0)
            padding_top = '2px'
        style = stylesheet.STYLE_QGROUPBOX.replace('$PADDING_TOP', padding_top)
        self.layout().setContentsMargins(*margin)
        self.setStyleSheet(style)
        super(GroupWidget, self).setTitle(text)

    def add_node_widget(self, widget):
        self.layout().addWidget(widget)

    def get_node_widget(self):
        return self.layout().itemAt(0).widget()


class AbstractWidget(QtWidgets.QGraphicsWidget):
    def __init__(self, parent=None):
        super(AbstractWidget, self).__init__(parent)
        self.resizing = False

    def mousePressEvent(self, event) -> None:
        if int(event.modifiers()) & QtCore.Qt.ShiftModifier:
            self.resizing = True
            if constants.DEBUG_TUPLE_NODE_SCALE:
                print("Node is scaling!")
            self.setCursor(QtCore.Qt.SizeAllCursor)
        else:
            super(AbstractWidget, self).mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.resizing:
            past_pos = self.scenePos()
            past_width = self.size().width()
            past_height = self.size().height()
            current_pos = self.mapToScene(event.pos())
            current_width = current_pos.x() - past_pos.x() if current_pos.x() >= past_pos.x() else past_width
            current_height = current_pos.y() - past_pos.y() if current_pos.y() >= past_pos.y() else past_height
            if current_width >= self.childItems()[0].widget().minimumSize().width() and \
                    current_height >= self.childItems()[0].widget().minimumSize().height():
                self.resize(current_width, current_height)
            if constants.DEBUG_TUPLE_NODE_SCALE:
                print("DEBUG TUPLE NODE SCALE CURRENT SIZE:", current_width, current_height)
        else:
            super(AbstractWidget, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self.resizing:
            self.resizing = False
            self.setCursor(QtCore.Qt.ArrowCursor)
        else:
            super(AbstractWidget, self).mouseReleaseEvent(event)


class TruthWidget(QtWidgets.QGraphicsWidget):
    def __init__(self, truth=True, parent=None):
        super(TruthWidget, self).__init__(parent)
        # new checkbox
        self.truth_checkbox = QtWidgets.QCheckBox("Truth")
        self.truth_checkbox.setChecked(truth)
        self.truth_checkbox.setStyleSheet(stylesheet.STYLE_QCHECKBOX)

        # set font
        font = self.truth_checkbox.font()
        font.setPointSize(8)
        self.truth_checkbox.setFont(font)

        # add into group
        proxywidget = QtWidgets.QGraphicsProxyWidget()
        proxywidget.setWidget(self.truth_checkbox)
        self.layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Horizontal)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.addItem(proxywidget)
        self.setLayout(self.layout)

    def sizeHint(self, which=None, constraint=None) -> QtCore.QSizeF:
        width = self.truth_checkbox.width() + 5
        height = self.truth_checkbox.height() + 5
        return QtCore.QSizeF(width, height)

    def boundingRect(self) -> QtCore.QRectF:
        return QtCore.QRectF(0, 0,
                             self.truth_checkbox.width() + 5,
                             self.truth_checkbox.height() + 5)


class LogicWidget(QtWidgets.QGraphicsWidget, serializable.Serializable):
    def __init__(self, parent=None):
        super(LogicWidget, self).__init__(parent)
        self.resizing = False
        self.setFlags(QtWidgets.QGraphicsItem.ItemIsMovable | QtWidgets.QGraphicsItem.ItemIsSelectable)
        self.input_port = port.Port(constants.INPUT_NODE_TYPE, True, self)
        self.output_port = port.Port(constants.OUTPUT_NODE_TYPE, True, self)
        self.layout = QtWidgets.QGraphicsLinearLayout()
        self.setZValue(constants.Z_VAL_NODE)
        self.logic_combobox_input = QtWidgets.QComboBox()
        self.logic_combobox_output = QtWidgets.QComboBox()
        self.design_ui()

        # Animation
        self.next_attribute = list()
        self.last_attribute = list()
        self.next_logic = list()
        self.last_logic = list()
        self.attribute_animation = False

        # Colliding
        self.moving = False
        self.colliding_co = False

    def design_ui(self):
        # select logic
        self.logic_combobox_input.setStyleSheet(stylesheet.STYLE_QCOMBOBOX)
        self.logic_combobox_input.setMaximumHeight(20)
        logic_list_input = QtWidgets.QListView(self.logic_combobox_input)
        logic_list_input.setStyleSheet(stylesheet.STYLE_QLISTVIEW)
        self.logic_combobox_input.setView(logic_list_input)
        self.logic_combobox_input.addItems(("And", "Or", "Not"))
        self.logic_combobox_input.clearFocus()

        self.logic_combobox_output.setStyleSheet(stylesheet.STYLE_QCOMBOBOX)
        self.logic_combobox_input.setMaximumHeight(20)
        logic_list_output = QtWidgets.QListView(self.logic_combobox_output)
        logic_list_output.setStyleSheet(stylesheet.STYLE_QLISTVIEW)
        self.logic_combobox_output.setView(logic_list_output)
        self.logic_combobox_output.addItems(("And", "Or", "Not"))
        self.logic_combobox_output.clearFocus()

        group = GroupWidget("Logical Controller")
        group.add_node_widget(self.logic_combobox_input)
        group.add_node_widget(self.logic_combobox_output)
        proxywidget = QtWidgets.QGraphicsProxyWidget()
        proxywidget.setWidget(group)
        self.layout.addItem(proxywidget)
        self.setLayout(self.layout)

    def get_port_position(self, port_type, port_truth):
        if port_truth:
            if port_type == constants.INPUT_NODE_TYPE:
                return self.input_port.scenePos() + QtCore.QPointF(0, 11)
            else:
                return self.output_port.scenePos() + QtCore.QPointF(0, 11)

    def update_pipe_position(self):
        self.input_port.update_pipes_position()
        self.output_port.update_pipes_position()

    def add_next_attribute(self, widget):
        self.next_attribute.append(widget)

    def add_last_attribute(self, widget):
        self.last_attribute.append(widget)

    def add_next_logic(self, widget):
        self.next_logic.append(widget)

    def add_last_logic(self, widget):
        self.last_logic.append(widget)

    def remove_next_attribute(self, widget):
        self.next_attribute.remove(widget)

    def remove_last_attribute(self, widget):
        self.last_attribute.remove(widget)

    def remove_next_logic(self, widget):
        self.next_logic.remove(widget)

    def remove_last_logic(self, widget):
        self.last_logic.remove(widget)

    def start_pipe_animation(self):
        self.output_port.start_pipes_animation()
        self.input_port.start_pipes_animation()
        self.attribute_animation = True

        for node in self.next_attribute:
            if not node.attribute_animation:
                node.start_pipe_animation()

        for node in self.last_attribute:
            if not node.attribute_animation:
                node.start_pipe_animation()

        for logic in self.next_logic:
            if not logic.attribute_animation:
                logic.start_pipe_animation()

        for logic in self.last_logic:
            if not logic.attribute_animation:
                logic.start_pipe_animation()

    def end_pipe_animation(self):
        self.output_port.end_pipes_animation()
        self.input_port.end_pipes_animation()
        self.attribute_animation = False

        for node in self.next_attribute:
            if node.attribute_animation:
                node.end_pipe_animation()

        for node in self.last_attribute:
            if node.attribute_animation:
                node.end_pipe_animation()

        for logic in self.next_logic:
            if logic.attribute_animation:
                logic.end_pipe_animation()

        for logic in self.last_logic:
            if logic.attribute_animation:
                logic.end_pipe_animation()

    @staticmethod
    def colliding_judge_pipe(logic_widget, item):
        for pipe_widget in logic_widget.input_port.pipes:
            if pipe_widget is item:
                return True
        for pipe_widget in logic_widget.output_port.pipes:
            if pipe_widget is item:
                return True
        return False

    def colliding_detection(self):
        colliding_items = self.scene().collidingItems(self, QtCore.Qt.IntersectsItemBoundingRect)
        for colliding_item in colliding_items:
            if isinstance(colliding_item, pipe.Pipe):
                if not self.colliding_judge_pipe(self, colliding_item):
                    self.colliding_co = True
                    self.update()
                    return colliding_item
            self.colliding_co = False
            self.update()

    def colliding_release(self):
        if self.colliding_co:
            pipe_item = self.colliding_detection()

            output_node = pipe_item.get_output_node()
            input_node = pipe_item.get_input_node()
            if isinstance(input_node, AttributeWidget):
                output_node.remove_next_attribute(input_node)
                self.add_next_attribute(input_node)
            else:
                output_node.remove_next_logic(input_node)
                self.add_next_logic(input_node)
            output_node.add_next_logic(self)
            if isinstance(output_node, AttributeWidget):
                input_node.remove_last_attribute(output_node)
                self.add_last_attribute(output_node)
            else:
                input_node.remove_last_logic(output_node)
                self.add_last_logic(output_node)
            input_node.add_last_logic(self)

            input_port = pipe_item.get_input_type_port()
            pipe_widget = pipe.Pipe(self.output_port, input_port, self)
            self.scene().addItem(pipe_widget)
            self.scene().view.pipes.append(pipe_widget)
            pipe_item.end_port = self.input_port

            input_port.remove_pipes(pipe_item)
            input_port.add_pipes(pipe_widget)
            self.input_port.add_pipes(pipe_item)
            self.output_port.add_pipes(pipe_widget)

            self.update_pipe_position()
            input_node.update_pipe_position()
            output_node.update_pipe_position()

            if output_node.attribute_animation:
                self.start_pipe_animation()

        self.moving = False
        self.colliding_co = False

    def paint(self, painter, option, widget=None) -> None:
        super(LogicWidget, self).paint(painter, option, widget)
        self.input_port.setPos(-12, self.size().height() / 2 - 3)
        self.output_port.setPos(self.size().width() - 12, self.size().height() / 2 - 3)

        if self.colliding_co:
            pen = QtGui.QPen(QtGui.QColor(230, 0, 0, 100), 2)
        elif self.isSelected():
            pen = QtGui.QPen(QtGui.QColor(255, 229, 153, 255), 2)
        else:
            pen = QtGui.QPen(QtGui.QColor(15, 242, 254, 255), 1)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(0, 0, self.size().width(), self.size().height(), 2, 2)

    def mouseMoveEvent(self, event: 'QtWidgets.QGraphicsSceneMouseEvent') -> None:
        self.moving = True
        super(LogicWidget, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: 'QtWidgets.QGraphicsSceneMouseEvent') -> None:
        self.colliding_release()
        super(LogicWidget, self).mouseReleaseEvent(event)

    def moveEvent(self, event: 'QtWidgets.QGraphicsSceneMoveEvent') -> None:
        super(LogicWidget, self).moveEvent(event)
        if self.moving:
            self.colliding_detection()
        self.update_pipe_position()

    def serialize(self):
        next_attribute_widgets = list()
        next_logic_widgets = list()
        last_attribute_widgets = list()
        last_logic_widgets = list()
        for next_attribute_widget in self.next_attribute:
            next_attribute_widgets.append(next_attribute_widget.id)
        for next_logic_widget in self.next_logic:
            next_logic_widgets.append(next_logic_widget.id)
        for last_attribute_widget in self.last_attribute:
            last_attribute_widgets.append(last_attribute_widget.id)
        for last_logic_widget in self.last_logic:
            last_logic_widgets.append(last_logic_widget.id)

        return OrderedDict([
            ('id', self.id),
            ('x', self.scenePos().x()),
            ('y', self.scenePos().y()),
            ('input truth', self.logic_combobox_input.currentIndex()),
            ('output truth', self.logic_combobox_output.currentIndex()),
            ('input port', self.input_port.serialize()),
            ('output port', self.output_port.serialize()),
            ('next attribute widgets', next_attribute_widgets),
            ('next logic widgets', next_logic_widgets),
            ('last attribute widgets', last_attribute_widgets),
            ('last logic widgets', last_logic_widgets)
        ])

    def deserialize(self, data, hashmap: dict, view=None, flag=True):
        if flag:
            # added into scene and view
            view.current_scene.addItem(self)
            view.logic_widgets.append(self)
            # id and hashmap
            self.id = data['id']
            hashmap[data['id']] = self
            # geometry and contents
            self.setPos(data['x'], data['y'])
            self.logic_combobox_input.setCurrentIndex(data['input truth'])
            self.logic_combobox_output.setCurrentIndex(data['output truth'])
            # ports
            self.input_port.deserialize(data['input port'], hashmap, view, flag=True)
            self.output_port.deserialize(data['output port'], hashmap, view, flag=True)
            return True
        else:
            pass


class AttributeImage(QtWidgets.QGraphicsWidget):
    def __init__(self, parent=None):
        super(AttributeImage, self).__init__(parent)
        self.video = parent
        self.file_url = None


class ChangeImageOrVideo(QtWidgets.QLabel):
    def __init__(self, label_type: str, parent, text):
        super(ChangeImageOrVideo, self).__init__(text)
        self.label_type = label_type
        self.parent = parent
        self.setStyleSheet(stylesheet.STYLE_QLABEL)

    def mousePressEvent(self, ev: QtGui.QMouseEvent) -> None:
        super(ChangeImageOrVideo, self).mousePressEvent(ev)
        if self.label_type == "Cover":
            self.parent.turn_image()
        elif self.label_type == "File":
            self.parent.turn_file()


class AttributeFile(QtWidgets.QGraphicsWidget, serializable.Serializable):
    def __init__(self, parent=None):
        super(AttributeFile, self).__init__(parent)
        self.setZValue(constants.Z_VAL_NODE)

        # widget
        self.image = AttributeImage()
        self.image.setMinimumSize(100, 100)
        self.image.setMaximumSize(100, 100)
        self.image.setAutoFillBackground(True)
        palette = self.image.palette()
        palette.setBrush(QtGui.QPalette.Window, QtGui.QBrush(QtGui.QPixmap("Resources/Attribute Flag/video.png").scaled(
            self.image.size().width(),
            self.image.size().height(),
            QtCore.Qt.IgnoreAspectRatio,
            QtCore.Qt.SmoothTransformation
        )))
        self.image.setPalette(palette)

        self.label_item = SimpleTextField("Description", self)
        self.label_item.setFont(QtGui.QFont("LucidaMacBold", 8))

        self.change_image_text = ChangeImageOrVideo("Cover", self, "Cover")
        self.change_video_text = ChangeImageOrVideo("File", self, "File")
        self.proxy_image_text = QtWidgets.QGraphicsProxyWidget()
        self.proxy_video_text = QtWidgets.QGraphicsProxyWidget()
        self.proxy_image_text.setZValue(constants.Z_VAL_NODE)
        self.proxy_video_text.setZValue(constants.Z_VAL_NODE)
        self.proxy_image_text.setWidget(self.change_image_text)
        self.proxy_video_text.setWidget(self.change_video_text)

        # layout
        self.layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Vertical)
        self.layout.setSpacing(15)
        self.control_layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Horizontal)
        self.control_layout.addItem(self.proxy_image_text)
        self.control_layout.addItem(self.proxy_video_text)
        self.layout.addItem(QtWidgets.QGraphicsWidget(self.label_item))
        self.layout.addItem(self.control_layout)
        self.layout.addItem(self.image)
        self.setLayout(self.layout)

        # store
        self.image_url = r"Resources/Attribute Flag/video.png"

    def turn_image(self):
        image_url, _ = QtWidgets.QFileDialog.getOpenFileName(None, "select image", "", "*.png *.jpg")
        if image_url:
            self.image_url = image_url
            palette = self.image.palette()
            palette.setBrush(QtGui.QPalette.Window, QtGui.QBrush(QtGui.QPixmap(image_url).scaled(
                self.image.size().width(),
                self.image.size().height(),
                QtCore.Qt.IgnoreAspectRatio,
                QtCore.Qt.SmoothTransformation
            )))
            self.image.setPalette(palette)

    def turn_file(self):
        file_url, _ = QtWidgets.QFileDialog.getOpenFileName(None, "select files", "", "any file (*.*)")
        if file_url:
            self.image.file_url = file_url

    def serialize(self):
        return OrderedDict([
            ("id", self.id),
            ("text", self.label_item.toPlainText()),
            ("cover", self.image_url),
            ("file", self.image.file_url)
        ])

    def deserialize(self, data, hashmap: dict, view=None, flag=True):
        # id and hashmap
        self.id = data['id']
        hashmap[data['id']] = self
        # text
        self.label_item.setPlainText(data['text'])
        # image
        self.image_url = data['cover']
        palette = self.image.palette()
        palette.setBrush(QtGui.QPalette.Window, QtGui.QBrush(QtGui.QPixmap(self.image_url).scaled(
            self.image.size().width(),
            self.image.size().height(),
            QtCore.Qt.IgnoreAspectRatio,
            QtCore.Qt.SmoothTransformation
        )))
        self.image.setPalette(palette)
        # file
        self.image.file_url = data['file']
        return True


class AttributeWidget(QtWidgets.QGraphicsWidget, serializable.Serializable):
    display_name_changed = QtCore.pyqtSignal(str)
    draw_label = None

    def __init__(self):
        super(AttributeWidget, self).__init__()
        # SET BASIC FUNCTION.
        self.name = "Node"
        self.setFlags(QtWidgets.QGraphicsWidget.ItemIsSelectable | QtWidgets.QGraphicsWidget.ItemIsFocusable |
                      QtWidgets.QGraphicsWidget.ItemSendsGeometryChanges | QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setCacheMode(QtWidgets.QGraphicsItem.DeviceCoordinateCache)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setAcceptHoverEvents(True)
        self.setZValue(constants.Z_VAL_NODE)

        # COLORS
        self.color = (229, 255, 255, 125)
        self.border_color = (46, 57, 66, 255)
        self.selected_color = (255, 255, 255, 30)
        self.selected_border_color = (254, 207, 42, 255)

        # LAYOUTS
        #   create
        self.layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Horizontal)
        self.input_layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Vertical)
        self.output_layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Vertical)
        self.attribute_layout = QtWidgets.QGraphicsLinearLayout(QtCore.Qt.Vertical)
        #   sapcing
        self.layout.setSpacing(0)
        self.input_layout.setSpacing(0)
        self.output_layout.setSpacing(0)
        self.attribute_layout.setSpacing(0)
        #   margin
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.input_layout.setContentsMargins(0, 0, 0, 0)
        self.output_layout.setContentsMargins(0, 0, 0, 0)
        self.attribute_layout.setContentsMargins(0, 0, 0, 5)

        # WIDGETS
        #   title name widget
        self.attribute_widget = SubConstituteWidget(self)
        #   port widgets
        self.true_input_port = port.Port(constants.INPUT_NODE_TYPE, True, self)
        self.true_output_port = port.Port(constants.OUTPUT_NODE_TYPE, True, self)
        self.false_input_port = port.Port(constants.INPUT_NODE_TYPE, False, self)
        self.false_output_port = port.Port(constants.OUTPUT_NODE_TYPE, False, self)
        self.true_input_port.setMaximumSize(25, 25)
        self.true_input_port.setMinimumSize(25, 25)
        self.true_output_port.setMaximumSize(25, 25)
        self.true_output_port.setMinimumSize(25, 25)
        self.false_input_port.setMaximumSize(25, 25)
        self.false_input_port.setMinimumSize(25, 25)
        self.false_output_port.setMaximumSize(25, 25)
        self.false_output_port.setMinimumSize(25, 25)
        # IMPLEMENT WIDGETS
        #   layout
        self.setLayout(self.layout)
        self.layout.addItem(self.input_layout)
        self.layout.addStretch(1)
        self.layout.addItem(self.attribute_layout)
        self.layout.addStretch(1)
        self.layout.addItem(self.output_layout)
        #  input layout
        self.input_layout.addItem(self.true_input_port)
        self.input_layout.addStretch(1)
        self.input_layout.addItem(self.false_input_port)
        # attribute layout
        self.attribute_layout.addItem(self.attribute_widget)
        self.attribute_layout.setAlignment(self.attribute_widget, QtCore.Qt.AlignCenter)
        # output layout
        self.output_layout.addItem(self.true_output_port)
        self.output_layout.addStretch(1)
        self.output_layout.addItem(self.false_output_port)

        # RESIZE
        self.resizing = False

        # MOVE
        self.moving = False
        self.colliding_type = constants.COLLIDING_ATTRIBUTE
        self.colliding_co = False
        self.colliding_parent = False
        self.colliding_child = False
        self.colliding_inside = False

        # ANAMATION
        self.attribute_animation = False
        self.next_attribute = list()
        self.last_attribute = list()
        self.next_logic = list()
        self.last_logic = list()
        self.attribute_sub_widgets = list()

        # SCENE
        self.sub_scene = None

    def paint(self, painter, option, widget=None) -> None:
        painter.save()

        # draw border
        bg_border = 1.0
        radius = 2
        rect = QtCore.QRectF(
            0.5 - (bg_border / 2),
            0.5 - (bg_border / 2),
            self.boundingRect().width() + bg_border,
            self.boundingRect().height() + bg_border
        )
        border_color = QtGui.QColor(*self.border_color)
        path = QtGui.QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        # draw background
        rect = self.boundingRect()
        painter.setBrush(QtGui.QColor(*self.color) if not self.isSelected() else QtGui.QColor(*self.selected_color))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(rect, radius, radius)

        # draw border
        border_width = 0.8
        if self.isSelected() and constants.NODE_SEL_BORDER_COLOR:
            border_width = 1.2
            border_color = QtGui.QColor(*constants.NODE_SEL_BORDER_COLOR)
        border_rect = QtCore.QRectF(rect.left() - (border_width / 2),
                                    rect.top() - (border_width / 2),
                                    rect.width() + border_width,
                                    rect.height() + border_width)
        pen = QtGui.QPen(border_color, border_width)
        path = QtGui.QPainterPath()
        path.addRoundedRect(border_rect, radius, radius)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.setPen(pen if not self.colliding_co else
                       QtGui.QPen(QtGui.QColor(230, 0, 0, 100), 2))
        painter.drawPath(path)

        painter.restore()

    def text_change_node_shape(self):
        # text
        self.attribute_widget.updateGeometry()
        self.attribute_widget.update()
        #  layout
        self.prepareGeometryChange()
        self.layout.invalidate()
        self.layout.activate()
        self.updateGeometry()
        self.update()
        self.attribute_layout.updateGeometry()
        self.attribute_layout.invalidate()
        # pipe position
        self.update_pipe_position()
        self.update_pipe_parent_position()

    def mouse_update_node_size(self, event):
        if event.type() == QtCore.QEvent.GraphicsSceneMousePress and not self.parentItem():
            self.resizing = True
            self.setCursor(QtCore.Qt.SizeAllCursor)
        elif event.type() == QtCore.QEvent.GraphicsSceneMouseRelease and not self.parentItem():
            self.resizing = False
            self.setCursor(QtCore.Qt.ArrowCursor)
        elif event.type() == QtCore.QEvent.GraphicsSceneMouseMove and not self.parentItem():
            past_pos = self.scenePos()
            past_width = self.size().width()
            past_height = self.size().height()
            current_pos = self.mapToScene(event.pos())
            current_width = current_pos.x() - past_pos.x() if current_pos.x() >= past_pos.x() else past_width
            current_height = current_pos.y() - past_pos.y() if current_pos.y() >= past_pos.y() else past_height
            self.resize(current_width, current_height)
            self.update_pipe_position()

            if constants.DEBUG_TUPLE_NODE_SCALE:
                print(current_width, current_height)

    def get_port_position(self, port_type, port_truth):
        pos = QtCore.QPointF(0, 0)
        if port_type == constants.INPUT_NODE_TYPE:
            if port_truth:
                pos = self.true_input_port.scenePos() + QtCore.QPointF(0, 11)
            else:
                pos = self.false_input_port.scenePos() + QtCore.QPointF(0, 11)
        elif port_type == constants.OUTPUT_NODE_TYPE:
            if port_truth:
                pos = self.true_output_port.scenePos() + QtCore.QPointF(11, 11)
            else:
                pos = self.false_output_port.scenePos() + QtCore.QPointF(11, 11)
        return pos

    def add_new_subwidget(self):
        subwidget = AttributeWidget()
        self.attribute_layout.addItem(subwidget)
        self.attribute_sub_widgets.append(subwidget)
        self.scene().view.attribute_widgets.append(subwidget)
        self.text_change_node_shape()
        self.update_pipe_position()

        parent = self
        while parent.parentItem():
            parent = parent.parentItem()
            parent.text_change_node_shape()
            parent.update_pipe_position()

        self.scene().view.history.store_history("Add New Subwidget")

    def add_file(self):
        file = AttributeFile(self)
        self.attribute_layout.addItem(file)
        self.attribute_sub_widgets.append(file)

        self.text_change_node_shape()
        self.update_pipe_position()

        parent = self
        while parent.parentItem():
            parent = parent.parentItem()
            parent.text_change_node_shape()
            parent.update_pipe_position()

        self.scene().view.history.store_history("Add New FIle")

    @staticmethod
    def move_up_widget(widget):
        parent = widget.parentItem()
        index = 0
        for i in range(parent.attribute_layout.count()):
            index = i
            if widget == parent.attribute_layout.itemAt(i).graphicsItem():
                break
        if index == 0:
            return
        else:
            parent.attribute_layout.removeAt(index)
            parent.attribute_layout.insertItem(index - 1, widget)

    @staticmethod
    def move_down_widget(widget):
        parent = widget.parentItem()
        index = 0
        for i in range(parent.attribute_layout.count()):
            index = i
            if widget == parent.attribute_layout.itemAt(i).graphicsItem():
                break
        if index == parent.attribute_layout.count() - 1:
            return
        else:
            parent.attribute_layout.removeAt(index)
            parent.attribute_layout.insertItem(index + 1, widget)

    def add_exist_subwidget(self, subwidget):
        self.attribute_layout.addItem(subwidget)
        self.attribute_sub_widgets.append(subwidget)
        subwidget.setParentItem(self)
        self.text_change_node_shape()
        self.update_pipe_position()

        parent = self
        while parent.parentItem():
            parent = parent.parentItem()
            parent.text_change_node_shape()
            parent.update_pipe_position()

    def delete_subwidget(self, subwidget):
        self.attribute_layout.removeItem(subwidget)
        self.attribute_sub_widgets.remove(subwidget)
        subwidget.setParentItem(None)
        self.text_change_node_shape()
        self.update_pipe_position()

    def colliding_judge_sub(self, parent_widget, item):
        while parent_widget.attribute_sub_widgets:
            for sub_widget in parent_widget.attribute_sub_widgets:
                if isinstance(sub_widget, AttributeWidget):
                    if sub_widget is item:
                        self.colliding_child = True
                        self.update()
                        return 1
                    parent_widget = sub_widget
                    if self.colliding_judge_sub(parent_widget, item):
                        return 1

    def colliding_judge_parent(self, parent_widget, item):
        while parent_widget.parentItem():
            parent_widget = parent_widget.parentItem()
            if parent_widget is item:
                self.colliding_parent = True
                self.update()
                return 1

    @staticmethod
    def colliding_judge_pipe(attribute_widget, item):
        for pipe_widget in attribute_widget.true_input_port.pipes:
            if pipe_widget is item:
                return True
        for pipe_widget in attribute_widget.true_output_port.pipes:
            if pipe_widget is item:
                return True
        for pipe_widget in attribute_widget.false_input_port.pipes:
            if pipe_widget is item:
                return True
        for pipe_widget in attribute_widget.false_output_port.pipes:
            if pipe_widget is item:
                return True
        for sub_widget in attribute_widget.attribute_sub_widgets:
            if sub_widget.colliding_judge_pipe(sub_widget, item):
                return True
        return False

    def colliding_detection(self):
        colliding_items = self.scene().collidingItems(self, QtCore.Qt.IntersectsItemBoundingRect)
        for item in colliding_items:
            if isinstance(item, AttributeWidget):
                self.colliding_type = constants.COLLIDING_ATTRIBUTE
                flag_child = self.colliding_judge_sub(self, item)
                flag_parent = self.colliding_judge_parent(self, item)
                if not flag_parent and not flag_child:
                    self.colliding_co = True
                if flag_parent:
                    self.colliding_inside = True
                self.update()

                flag_pipe = False
                for left_item in colliding_items[colliding_items.index(item):]:
                    if isinstance(left_item, pipe.Pipe):
                        if not self.colliding_judge_pipe(self, left_item):
                            flag_pipe = True
                            continue

                if not flag_child:
                    return item

                if constants.DEBUG_COLLIDING:
                    print("****************attr**************************")
                    print("DEBUG COLLIDING status: ", "\nchild: ", self.colliding_child,
                          "\nparent: ", self.colliding_parent, "\ncommon co: ", self.colliding_co,
                          "\ninside: ", self.colliding_inside, "\nreturn item: ", item,
                          "\ntype: ", self.colliding_type, "\nflag pipe", flag_pipe)
                    print("**********************************************")

            elif isinstance(item, pipe.Pipe):

                if not self.colliding_judge_pipe(self, item):
                    self.colliding_type = constants.COLLIDING_PIPE
                    self.colliding_co = True
                    self.update()

                    if constants.DEBUG_COLLIDING:
                        print("****************pipe**************************")
                        print("DEBUG COLLIDING status: ", "\nchild: ", self.colliding_child,
                              "\nparent: ", self.colliding_parent, "\ncommon co: ", self.colliding_co,
                              "\ninside: ", self.colliding_inside, "\nreturn item: ", item,
                              "\ntype: ", self.colliding_type)
                        print("**********************************************")

                    return item

            else:

                self.colliding_co = False
                self.colliding_type = constants.COLLIDING_ATTRIBUTE
                self.colliding_inside = False

        self.update()

    def colliding_release(self, event):
        if self.colliding_type == constants.COLLIDING_ATTRIBUTE:
            if self.colliding_co and self.colliding_parent:
                item = self.colliding_detection()
                self.parentItem().delete_subwidget(self)
                item.add_exist_subwidget(self)
            elif not self.colliding_co and self.colliding_parent and not self.colliding_inside:
                self.parentItem().delete_subwidget(self)
                self.setPos(event.scenePos())
            elif not self.colliding_co and self.colliding_parent and self.colliding_inside:
                self.parentItem().text_change_node_shape()
            elif self.colliding_co and not self.colliding_parent:
                self.colliding_detection().add_exist_subwidget(self)
            self.colliding_co = False
            self.colliding_parent = False
            self.colliding_child = False
            self.colliding_inside = False
            self.moving = False
            self.update()

        elif self.colliding_type == constants.COLLIDING_PIPE:
            item = self.colliding_detection()

            if self.parentItem():
                self.parentItem().delete_subwidget(self)
                self.setPos(event.scenePos())

            output_node = item.get_output_node()
            input_node = item.get_input_node()
            if isinstance(input_node, AttributeWidget):
                output_node.remove_next_attribute(input_node)
                self.add_next_attribute(input_node)
            else:
                output_node.remove_next_logic(input_node)
                self.add_next_logic(input_node)
            output_node.add_next_attribute(self)
            if isinstance(output_node, AttributeWidget):
                input_node.remove_last_attribute(output_node)
                self.add_last_attribute(output_node)
            else:
                input_node.remove_last_logic(output_node)
                self.add_last_logic(output_node)
            input_node.add_last_attribute(self)

            if isinstance(input_node, AttributeWidget):
                pipe_widget = pipe.Pipe(self.true_output_port, input_node.true_input_port, self)
            else:
                pipe_widget = pipe.Pipe(self.true_output_port, input_node.input_port, self)
            self.scene().addItem(pipe_widget)
            self.scene().view.pipes.append(pipe_widget)

            item.get_input_type_port().add_pipes(pipe_widget)
            item.get_input_type_port().remove_pipes(item)
            self.true_input_port.add_pipes(item)
            self.true_output_port.add_pipes(pipe_widget)
            if item.end_port.port_type == constants.OUTPUT_NODE_TYPE:
                item.start_port = self.true_input_port
                item.update_position()
            else:
                item.end_port = self.true_input_port
                item.update_position()

            self.colliding_co = False
            self.colliding_parent = False
            self.colliding_child = False
            self.colliding_inside = False
            self.moving = False
            self.colliding_type = constants.COLLIDING_ATTRIBUTE
            self.update()
            input_node.update_pipe_position()
            output_node.update_pipe_position()

            if output_node.attribute_animation:
                self.start_pipe_animation()

    def update_scene_rect(self):
        self.scene().setSceneRect(self.scene().itemsBoundingRect())

    def update_pipe_parent_position(self):
        parent_item = self
        while parent_item.parentItem():
            parent_item.parentItem().update_pipe_position()
            parent_item = parent_item.parentItem()

    def update_pipe_position(self):
        self.true_input_port.update_pipes_position()
        self.true_output_port.update_pipes_position()
        self.false_input_port.update_pipes_position()
        self.false_output_port.update_pipes_position()
        for sub_widget in self.attribute_sub_widgets:
            if isinstance(sub_widget, AttributeWidget):
                sub_widget.update_pipe_position()

    def add_next_attribute(self, widget):
        self.next_attribute.append(widget)

    def add_last_attribute(self, widget):
        self.last_attribute.append(widget)

    def add_next_logic(self, widget):
        self.next_logic.append(widget)

    def add_last_logic(self, widget):
        self.last_logic.append(widget)

    def set_sub_scene(self, scene_widget):
        self.sub_scene = scene_widget

    def remove_next_attribute(self, widget):
        self.next_attribute.remove(widget)

    def remove_last_attribute(self, widget):
        self.last_attribute.remove(widget)

    def remove_next_logic(self, widget):
        self.next_logic.remove(widget)

    def remove_last_logic(self, widget):
        self.last_logic.remove(widget)

    def remove_sub_scene(self):
        self.sub_scene = None

    def start_pipe_animation(self):
        self.true_output_port.start_pipes_animation()
        self.false_output_port.start_pipes_animation()
        self.true_input_port.start_pipes_animation()
        self.false_input_port.start_pipes_animation()
        self.attribute_animation = True

        for node in self.next_attribute:
            if not node.attribute_animation:
                node.start_pipe_animation()

        for node in self.last_attribute:
            if not node.attribute_animation:
                node.start_pipe_animation()

        for logic in self.next_logic:
            if not logic.attribute_animation:
                logic.start_pipe_animation()

        for logic in self.last_logic:
            if not logic.attribute_animation:
                logic.start_pipe_animation()

        for sub_node in self.attribute_sub_widgets:
            if not sub_node.attribute_animation:
                sub_node.start_pipe_animation()

    def end_pipe_animation(self):
        self.true_output_port.end_pipes_animation()
        self.false_output_port.end_pipes_animation()
        self.true_input_port.end_pipes_animation()
        self.false_input_port.end_pipes_animation()
        self.attribute_animation = False

        for node in self.next_attribute:
            if node.attribute_animation:
                node.end_pipe_animation()

        for node in self.last_attribute:
            if node.attribute_animation:
                node.end_pipe_animation()

        for logic in self.next_logic:
            if logic.attribute_animation:
                logic.end_pipe_animation()

        for logic in self.last_logic:
            if logic.attribute_animation:
                logic.end_pipe_animation()

        for sub_node in self.attribute_sub_widgets:
            if not sub_node.attribute_animation:
                sub_node.end_pipe_animation()

    def update_treelist(self):
        if self.sub_scene:
            iterator = QtWidgets.QTreeWidgetItemIterator(self.scene().view.mainwindow.scene_list)
            while iterator.value():
                scene_flag = iterator.value()
                iterator += 1
                if scene_flag.data(0, QtCore.Qt.ToolTipRole) is self.sub_scene:
                    scene_flag.setText(0, self.attribute_widget.label_item.toPlainText())

    def mousePressEvent(self, event) -> None:
        if int(event.modifiers()) & QtCore.Qt.ShiftModifier:
            self.mouse_update_node_size(event)
        else:
            super(AttributeWidget, self).mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        self.moving = True
        if self.resizing:
            self.mouse_update_node_size(event)
        else:
            super(AttributeWidget, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.colliding_release(event)
        if self.resizing:
            self.mouse_update_node_size(event)
        else:
            super(AttributeWidget, self).mouseReleaseEvent(event)

    def contextMenuEvent(self, event: 'QtWidgets.QGraphicsSceneContextMenuEvent') -> None:
        menu = QtWidgets.QMenu()
        menu.setStyleSheet(stylesheet.STYLE_QMENU)
        add_subwidget = menu.addAction("Add Subwidget")
        add_subwidget.setIcon(QtGui.QIcon("Resources/AttributeWidgetContextMenu/ADD SUBWIDGET.PNG"))
        add_video = menu.addAction("Add Video")
        add_video.setIcon(QtGui.QIcon("Resources/AttributeWidgetContextMenu/Add Video.png"))
        move_up = menu.addAction("Move Up")
        move_up.setIcon(QtGui.QIcon("Resources/AttributeWidgetContextMenu/Up.png"))
        move_down = menu.addAction("Move Down")
        move_down.setIcon(QtGui.QIcon("Resources/AttributeWidgetContextMenu/Down.png"))
        result = menu.exec(event.screenPos())
        if result == add_subwidget:
            self.add_new_subwidget()
        elif result == add_video:
            self.add_file()
        elif result == move_up and (isinstance(self.scene().itemAt(event.scenePos(), QtGui.QTransform()).parentItem(),
                                               AttributeWidget) or
                                    isinstance(self.scene().itemAt(event.scenePos(), QtGui.QTransform()),
                                               AttributeFile)):
            self.move_up_widget(self.scene().itemAt(event.scenePos(), QtGui.QTransform()))
        elif result == move_down and (isinstance(self.scene().itemAt(event.scenePos(), QtGui.QTransform()).parentItem(),
                                                 AttributeWidget) or
                                      isinstance(self.scene().itemAt(event.scenePos(), QtGui.QTransform()),
                                                 AttributeFile)):
            self.move_down_widget(self.scene().itemAt(event.scenePos(), QtGui.QTransform()))
        event.setAccepted(True)

    def moveEvent(self, event: 'QtWidgets.QGraphicsSceneMoveEvent') -> None:
        super(AttributeWidget, self).moveEvent(event)
        if self.moving:
            self.colliding_detection()
        self.update_pipe_position()

    def serialize(self):
        next_attribute_widgets = list()
        next_logic_widgets = list()
        last_attribute_widgets = list()
        last_logic_widgets = list()
        attribute_sub_widgets = list()
        for next_attribute_widget in self.next_attribute:
            next_attribute_widgets.append(next_attribute_widget.id)
        for next_logic_widget in self.next_logic:
            next_logic_widgets.append(next_logic_widget.id)
        for last_attribute_widget in self.last_attribute:
            last_attribute_widgets.append(last_attribute_widget.id)
        for last_logic_widget in self.last_logic:
            last_logic_widgets.append(last_logic_widget.id)
        for attribute_sub_widget in self.attribute_sub_widgets:
            if isinstance(attribute_sub_widget, AttributeWidget):
                attribute_sub_widgets.append(attribute_sub_widget.id)
            elif isinstance(attribute_sub_widget, AttributeFile):
                attribute_sub_widgets.append(attribute_sub_widget.serialize())

        return OrderedDict([
            ('id', self.id),
            ('width', self.size().width()),
            ('height', self.size().height()),
            ('x', self.scenePos().x()),
            ('y', self.scenePos().y()),
            ('contents', self.attribute_widget.label_item.toHtml()),
            ('input true port', self.true_input_port.serialize()),
            ('input false port', self.false_input_port.serialize()),
            ('output true port', self.true_output_port.serialize()),
            ('output false port', self.false_output_port.serialize()),
            ('next attribute widgets', next_attribute_widgets),
            ('next logic widgets', next_logic_widgets),
            ('last attribute widgets', last_attribute_widgets),
            ('last logic widgets', last_logic_widgets),
            ('attribute sub widgets', attribute_sub_widgets),
            ('sub scene', self.sub_scene.serialize() if self.sub_scene else None)
        ])

    def deserialize(self, data, hashmap: dict, view=None, flag=True):
        if flag:
            # added into current scene and view
            view.current_scene.addItem(self)
            view.attribute_widgets.append(self)
            # id and hashmap
            self.id = data['id']
            hashmap[data['id']] = self
            # geometry and contents
            self.setGeometry(data['x'], data['y'], data['width'], data['height'])
            self.attribute_widget.label_item.setHtml(data['contents'])
            # ports
            self.true_input_port.deserialize(data['input true port'], hashmap, view, flag=True)
            self.false_input_port.deserialize(data['input false port'], hashmap, view, flag=True)
            self.true_output_port.deserialize(data['output true port'], hashmap, view, flag=True)
            self.false_output_port.deserialize(data['output false port'], hashmap, view, flag=True)
            # sub scene
            if data['sub scene']:
                # save scene and flag
                last_scene_flag = view.current_scene_flag
                last_scene = view.current_scene

                # sub scene
                from GraphicsView.scene import Scene
                sub_scene_flag = QtWidgets.QTreeWidgetItem(
                    view.current_scene_flag,
                    (self.attribute_widget.label_item.toPlainText(),))
                sub_scene = Scene(sub_scene_flag, view, self)
                self.set_sub_scene(sub_scene)
                sub_scene_flag.setData(0, QtCore.Qt.ToolTipRole, sub_scene)

                view.current_scene = sub_scene
                view.current_scene_flag = sub_scene_flag

                sub_scene.deserialize(data['sub scene'], hashmap, view, True)
                sub_scene.deserialize(data['sub scene'], hashmap, view, False)

                # restore scene and flag
                view.current_scene = last_scene
                view.current_scene_flag = last_scene_flag
        return True
