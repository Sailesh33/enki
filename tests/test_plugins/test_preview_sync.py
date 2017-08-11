#!/usr/bin/env python3
# .. -*- coding: utf-8 -*-
#
# *************************************************************
# test_preview_sync.py - Unit tests for the Preview Sync module
# *************************************************************
#
# Imports
# =======
# Library imports
# ---------------
import unittest
from unittest.mock import patch, MagicMock
import os.path
import sys
#
# Local application imports
# -------------------------
# Do this before PyQt imports so that base will set up sip API correctly.
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                ".."))

import base
#
# Third-party library imports
# ---------------------------
from PyQt5.QtCore import Qt, QPoint, pyqtSlot
from PyQt5.QtTest import QTest
from PyQt5.QtGui import QTextCursor
#
# Local application imports
# -------------------------
from enki.core.core import core
from test_preview import PreviewTestCase, QGetObject
from base import requiresModule, WaitForSignal
import enki.plugins.preview
import enki.plugins.preview.preview_sync
from import_fail import ImportFail


@unittest.skipUnless(enki.plugins.preview.preview_sync.findApproxTextInTarget,
                     'Requires working TRE')
class Test(PreviewTestCase):
    # Web to code sync tests
    ##----------------------
    # To do: a test that verifies that mouse clicks produce a web to text sync.
    # The problem: I can't seem to simulate keyboard presses via either QTest
    # (for unknown reasons) or JavaScript (for security reasons). I therefore
     # doubt that I can simulate mouse clicks.

    # Test that simulated mouse clicks at beginning/middle/end produce correct ``jsClick`` values
    ##^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    def _jsOnClick(self):
        """Simulate a mouse click by calling ``window.onclick()`` in Javascript."""
        self._widget().webEngineView.page().runJavaScript('window.onclick();')

    def _wsLen(self):
        """The web text for web-to-text sync will have extra
        whitespace in it. But ``findText`` operates on a space-less
        version of the text. Determine how many whitespace characters
        preceed the text.
        """
        wtc = self._plainText()
        return len(wtc) - len(wtc.lstrip())

    def _testSyncString(self, s):
        """Given a string ``s``, place the cursor after it and simulate a click
        in the web view. Verify that the index produced by ``jsClick``
        is correct.

        Params:
        s - String after which cursor will be placed.
        """
        self._doBasicTest('rst')
        wsLen = self._wsLen()
        with patch('enki.plugins.preview.preview_sync.PreviewSync._onWebviewClick_') as _onWebviewClick:
            # Select the text in x, then simulate a mouse click.
            go = QGetObject()
            with WaitForSignal(go.got_object, 5000):
                self._widget().webEngineView.page().runJavaScript('window.find("{}"); window.onclick();'.format(s), lambda obj: go.got_object.emit(obj))

            # See if the index with whitespace added matches.
            args, kwargs = _onWebviewClick.call_args
            # args[1] is webIndex, the index of the found item.
            self.assertEqual(args[1], len(s) + wsLen)

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync2a(self):
        """TODO: simulate a click before the first letter. Select T, then move backwards using
        https://developer.mozilla.org/en-US/docs/Web/API/Selection.modify.
        For now, test after the letter T (the first letter).
        """
        self._testSyncString('T')

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync2(self):
        """Simulate a click after 'The pre' and check the resulting ``jsClick`` result."""
        self._testSyncString('The pre')

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync3(self):
        """Same as above, but with the entire string."""
        self._testSyncString(self.testText)

    # Test that sending a ``jsClick`` signal at beginning/middle/end moves cursor in code pane correctly
    # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    def _sendJsClick(self, index):
        """Send a ``jsClick`` signal then see if the code view gets sycned correctly.

        Params:
        index - The index into 'The preview text' string to send and check.
        """
        self._doBasicTest('rst')
        # Move the code cursor somewhere else, rather than index 0,
        # so working code must change its value.
        self._dock().previewSync._moveTextPaneToIndex(5)
        assert index != 5
        # Now, sync for a click at the given index into 'The preview text'.
        self._dock().previewSync._onWebviewClick(self._plainText(), self._wsLen() + index)
        # Check the new index, which should be 0.
        p = core.workspace().currentDocument().qutepart.textCursor().position()
        self.assertEqual(p, index)

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync4(self):
        """Test a click at the beginning of the string."""
        self._sendJsClick(0)

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync5(self):
        """Test a click at the middle of the string."""
        self._sendJsClick(8)

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync6(self):
        """Test a click at the end of the string."""
        self._sendJsClick(len(self.testText))

    # Misc tests
    ##^^^^^^^^^^
    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync8(self):
        """Test with javascript disabled."""
        # The ``_dock()`` method only works after the dock exists.
        # The method below creates it.
        self._doBasicTest('rst')
        self._dock()._onJavaScriptEnabledCheckbox(False)
        # Click. Nothing will happen, but make sure there's no assertion
        # or internal error.
        QTest.mouseClick(self._widget().webEngineView, Qt.LeftButton)

    # Code to web sync tests
    ##----------------------
    # Basic text to web sync
    ##^^^^^^^^^^^^^^^^^^^^^^
    def _textToWeb(self, s, testText='One\n\nTwo\n\nThree', checkText=True):
        """Move the cursor in the text pane. Make sure it moves
        to the matching location in the web pane.

        Params:
        s -  The string in the text pane to click before.
        testText - The ReST string to use.
        checkText - True if the text hilighted in the web dock should be
            compared to the text in s.
        """
        # Create multi-line text.
        self.testText = testText
        self._doBasicTest('rst')
        # Find the desired string.
        index = self.testText.index(s)
        # Make the cursor movement timer expire ASAP to reduce testing time.
        # However, I stil see failures in the with clause below with wait times
        # of 350 ms. ???
        self._dock().previewSync._cursorMovementTimer.setInterval(0)
        # Move to index 0. The restorepos plugin sometimes moves the cursor to
        # index, causing the call to _moveTextPaneToIndex to do nothing,
        # producing a test failure.
        self._dock().previewSync._moveTextPaneToIndex(0)
        # The cursor is already at index 0. Moving here
        # produces no cursorPositionChanged signal.
        assert index != 0
        # Move to the location of the string s in the text.
        # The sync won't happen until the timer expires; wait
        # for that.
        with base.WaitForSignal(self._dock().previewSync.textToPreviewSynced,
                                3500, True):
            self._dock().previewSync._moveTextPaneToIndex(index, False)
        # The web view should have the line containing s selected now.
        if checkText:
            self.assertTrue(s in self._widget().webEngineView.selectedText())

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync9(self):
        # Don't use One, which is an index of 0, which causes no
        # cursor movement and therefore no text to web sync.
        self._textToWeb('ne')

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync10(self):
        self._textToWeb('Two')

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync11(self):
        self._textToWeb('Three')

    # More complex test to web sync
    ##^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    @requiresModule('docutils')
    @unittest.expectedFailure
    @base.inMainLoop
    def test_sync12(self):
        """Tables with an embedded image cause findText to fail.
        """
        self._textToWeb('table', """
================  ========================
header1           header2
================  ========================
img               .. image:: img.png
text after img    text after img
================  ========================

text after table""", False)

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync14(self):
        """Tables without an embedded image work just fine.
        """

        # This test fails when not run in the main loop. I'm not sure why.
        self._textToWeb('table', """
================  ========================
header1           header2
================  ========================
img               image:: img.png
text after img    text after img
================  ========================

text after table""", True)

    def _row_span_rest(self):
        return """
+--------------------------------+-------------+
| Apple 1                        | Banana 2    |
+--------------------------------+             |
| Coco 3                         |             |
| Cherry 3                       | Bael 2      |
+--------------------------------+-------------+
| Text after block 1,2, and 3                  |
+----------------------------------------------+
"""

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync15(self):
        """Text after an image works just fine.
        """

        # Like test_sync14, this test fails when not run in the main loop. ???
        self._textToWeb('table', """
.. image:: img.png

Here is some text after a table.""", True)

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync16(self):
        """Tables with column spans produce out-of-order text, so sync in some rows
        containing a column span fails. The ReST below, copied as text after
        being redered to HTML, is:

        Apple 1
        Banana 2

        Bael 2
        Coco 3 Cherry 3
        Text after block 1,2, and 3

        Note the reordering: Bael 2 comes before Coco 3 in the plain text, but
        before it in the ReST. There's not much the approximate match can do to
        fix this.
        """
        self._textToWeb('Banana', self._row_span_rest(), True)

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync17(self):
        """A failing case of the above test series."""
        self._textToWeb('Bael', self._row_span_rest(), False)

    @requiresModule('docutils')
    @base.inMainLoop
    def test_sync18(self):
        """Verify that sync after the column span works."""
        self._textToWeb('Text', self._row_span_rest(), True)

    # Test no sync on hidden preview window
    ##^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    @base.inMainLoop
    @requiresModule('docutils')
    def test_sync13(self):
        self._doBasicTest('rst')
        self._dock().close()
        # Move the cursor. If there's no crash, we're OK.
        qp = core.workspace().currentDocument().qutepart
        cursor = qp.textCursor()
        cursor.setPosition(1, QTextCursor.MoveAnchor)
        qp.setTextCursor(cursor)

    @base.inMainLoop
    @requiresModule('docutils')
    def test_sync13a(self):
        """ Make sure sync stops if the Preview dock is hidden. See https://github.com/hlamer/enki/issues/352.
        """
        # First, open the preview dock.
        self._doBasicTest('rst')
        # Speed up the test by reducing the cursor movemovement timer's timeout. This can only be done when the preview dock is open. Record `ps`, since this won't be available when the Preview dock is hidden below.
        ps = self._dock().previewSync
        ps._cursorMovementTimer.setInterval(0)
        # Now, switch to a non-previewable file.
        self.createFile('foo.unpreviewable_extension', 'Junk')
        # Move the cursor. Make sure sync doesn't run.
        qp = core.workspace().currentDocument().qutepart
        # One way to tell: the background sync won't run, meaning the future won't change. I tried with ``mock.patch('enki.plugins.preview.preview_sync.PreviewSync.syncTextToPreview`) as syncTextToPreview:``, but ``syncTextToPreview.assert_not_called()`` always passed.
        f = ps._runLatest.future
        qp.cursorPosition = (100, 100)
        # Wait for Qt to process messages, such as the timer.
        QTest.qWait(0)
        self.assertEqual(f, ps._runLatest.future)

    # Cases for _alignScrollAmount
    ##^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    # When the source y (in global coordinates) is above the target
    # window. The best the algorithm can do is move to the top of the target
    # window.
    #
    # .. image:: preview_sync_source_above_target.png
    @base.inMainLoop
    def test_sync19(self):
        self._doBasicTest('rst')
        offset = self._dock().previewSync._alignScrollAmount(
            sourceGlobalTop=0,
            sourceCursorBottom=100,
            targetGlobalTop=200,
            targetCursorBottom=100,
            targetHeight=200,
            targetCursorHeight=10,
            padding=15)
        self.assertEqual(offset, -75)

    # When the source y (in global coordinates) is within the target
    # window, and the target y is equal to the source y.
    #
    # .. image:: preview_sync_source_aligned_target_equal.png
    @base.inMainLoop
    def test_sync20a(self):
        self._doBasicTest('rst')
        offset = self._dock().previewSync._alignScrollAmount(
            sourceGlobalTop=0,
            sourceCursorBottom=100,
            targetGlobalTop=0,
            targetCursorBottom=100,
            targetHeight=300,
            targetCursorHeight=10,
            padding=0)
        self.assertEqual(offset, 0)

    # When the source y (in global coordinates) is within the target
    # window, and the target y is above the source y.
    #
    # .. image:: preview_sync_source_aligned_target_above.png
    @base.inMainLoop
    def test_sync20b(self):
        self._doBasicTest('rst')
        offset = self._dock().previewSync._alignScrollAmount(
            sourceGlobalTop=0,
            sourceCursorBottom=100,
            targetGlobalTop=0,
            targetCursorBottom=0,
            targetHeight=300,
            targetCursorHeight=10,
            padding=0)
        self.assertEqual(offset, 100)

    # When the source y (in global coordinates) is within the target
    # window, and the target y is below the source y.
    #
    # .. image:: preview_sync_source_aligned_target_below.png
    @base.inMainLoop
    def test_sync20c(self):
        self._doBasicTest('rst')
        offset = self._dock().previewSync._alignScrollAmount(
            sourceGlobalTop=0,
            sourceCursorBottom=100,
            targetGlobalTop=0,
            targetCursorBottom=200,
            targetHeight=300,
            targetCursorHeight=10,
            padding=0)
        self.assertEqual(offset, -100)

    # When the source y (in global coordinates) is below the target window.
    #
    # .. image:: preview_sync_source_below_target.png
    @base.inMainLoop
    def test_sync21(self):
        self._doBasicTest('rst')
        offset = self._dock().previewSync._alignScrollAmount(
            sourceGlobalTop=300,
            sourceCursorBottom=100,
            targetGlobalTop=0,
            targetCursorBottom=100,
            targetHeight=200,
            targetCursorHeight=10,
            padding=15)
        self.assertEqual(offset, 85)

    # Test that no crashes occur if TRE isn't available or is old
    ##-----------------------------------------------------------
    def test_sync22(self):
        """Prevent TRE from being imported. Make sure there are no exceptions.
        """
        with ImportFail(['approx_match'], [enki.plugins.preview.preview_sync]):
            self.assertIsNone(enki.plugins.preview.preview_sync.findApproxTextInTarget)
        # Now, make sure that TRE imports correctly.
        self.assertTrue(enki.plugins.preview.preview_sync.findApproxTextInTarget)
#
# Main
# ====
# Run the unit tests in this file.
if __name__ == '__main__':
    unittest.main()
