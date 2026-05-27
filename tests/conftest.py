import sys
import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication required for any QThread instantiation."""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app
