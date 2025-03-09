import os
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog,
    QMessageBox, QCheckBox, QScrollArea, QLabel, QMenu, QTabWidget,
    QGroupBox, QSplitter, QStatusBar, QToolTip, QSizePolicy, QMainWindow
)
from PySide6.QtCore import QSettings, Qt, Signal, QTimer, QUrl, QMimeData
from PySide6.QtGui import QFont, QIcon, QShortcut, QKeySequence, QColor, QPalette, QFontMetrics


class FileCheckBox(QCheckBox):
    """Custom QCheckBox that emits a signal when right-clicked"""
    rightClicked = Signal(object)

    def __init__(self, text, file_path, parent=None):
        super().__init__(text, parent)
        self.file_path = Path(file_path)
        self.setStyleSheet("""
            QCheckBox {
                spacing: 4px;
                margin: 1px;
                padding: 1px;
                font-family: Arial;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                margin: 1px;
            }
            QCheckBox:hover {
                background-color: #e0f0ff;
                border-radius: 3px;
            }
        """)
        self.setCursor(Qt.PointingHandCursor)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy_action = menu.addAction("Copy File Content")
        remove_action = menu.addAction("Remove From List")

        action = menu.exec(self.mapToGlobal(event.pos()))
        if action == copy_action:
            self.parent().copy_file_code(self.file_path)
        elif action == remove_action:
            self.parent().remove_file(self.file_path)

        self.rightClicked.emit(self)


class ActionButton(QPushButton):
    """Custom styled button for actions"""

    def __init__(self, text, parent=None, icon=None, tooltip=""):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)

        # Apply styling
        self.setStyleSheet("""
            QPushButton {
                background-color: #f0f4f8;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 2px 10px;
                font-weight: 500;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: #e0f0ff;
                border: 1px solid #a0c0e0;
            }
            QPushButton:pressed {
                background-color: #c0d0e0;
            }
            QPushButton:disabled {
                background-color: #f0f0f0;
                color: #a0a0a0;
                border: 1px solid #d0d0d0;
            }
        """)

        if icon:
            self.setIcon(icon)

        if tooltip:
            self.setToolTip(tooltip)


class StatusLabel(QLabel):
    """Custom label for status indicators"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(24)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 14px;
                padding: 1px;
                margin: 1px;
            }
        """)

    def show_success(self, duration=1500):
        """Show success checkmark"""
        self.setText("✓")
        self.setStyleSheet("""
            QLabel {
                color: #00aa00;
                font-weight: bold;
                font-size: 14px;
            }
        """)
        QTimer.singleShot(duration, self.clear_status)

    def show_failure(self, duration=1500):
        """Show failure indicator"""
        self.setText("✗")
        self.setStyleSheet("""
            QLabel {
                color: #cc0000;
                font-weight: bold;
                font-size: 14px;
            }
        """)
        QTimer.singleShot(duration, self.clear_status)

    def show_warning(self, duration=1500):
        """Show warning indicator"""
        self.setText("!")
        self.setStyleSheet("""
            QLabel {
                color: #ee8800;
                font-weight: bold;
                font-size: 14px;
            }
        """)
        QTimer.singleShot(duration, self.clear_status)

    def clear_status(self):
        """Clear the status indicator"""
        self.setText("")
        self.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 14px;
                padding: 1px;
                margin: 1px;
            }
        """)


class CodeCombinerApp(QMainWindow):
    def __init__(self):
        super().__init__()

        # Initialize settings
        self.settings = QSettings("CodeCombiner", "CodeCombinerApp")
        self.file_paths = [Path(fp) for fp in self.settings.value("file_paths", [])]
        stored_dir = self.settings.value("selected_directory", "")
        self.selected_directory = Path(stored_dir) if stored_dir and Path(stored_dir).exists() else Path(
            __file__).resolve().parent

        # Initialize state variables
        self.checked_file_paths = set()
        self.checkboxes = []
        self.previous_versions = {}
        self.operation_labels = {}
        self.highlighted_checkbox = None
        self.directory_tabs = {}
        self.tab_file_checkboxes = {}

        # Set up the UI
        self.init_ui()

        # Set up keyboard shortcuts
        self.setup_shortcuts()

        # Display files
        self.filter_and_scan_file_paths()

        # Set window properties
        self.setWindowTitle("Code Combiner")
        self.resize(900, 800)
        self.setMinimumSize(800, 600)  # Set minimum window size to prevent buttons from disappearing
        self.setWindowIcon(QIcon.fromTheme("accessories-text-editor"))

    def setup_shortcuts(self):
        """Set up keyboard shortcuts for common operations"""
        # Copy combined code: Ctrl+Shift+C
        self.shortcut_copy_combined = QShortcut(QKeySequence("Ctrl+Shift+C"), self)
        self.shortcut_copy_combined.activated.connect(self.copy_combined_code)

        # Select all: Ctrl+A
        self.shortcut_select_all = QShortcut(QKeySequence("Ctrl+A"), self)
        self.shortcut_select_all.activated.connect(self.select_all_files)

        # Deselect all: Ctrl+D
        self.shortcut_deselect_all = QShortcut(QKeySequence("Ctrl+D"), self)
        self.shortcut_deselect_all.activated.connect(self.unselect_all_files)

        # Reload: F5
        self.shortcut_reload = QShortcut(QKeySequence("F5"), self)
        self.shortcut_reload.activated.connect(self.reload_files)

    def init_ui(self):
        # Main widget and layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        main_layout = QVBoxLayout(self.central_widget)
        main_layout.setSpacing(4)  # Reduced spacing from 8 to 4
        main_layout.setContentsMargins(8, 8, 8, 8)  # Reduced margins from 10 to 8

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Directory selection section
        directory_group = QGroupBox("Directory")
        directory_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)  # Make height fixed
        directory_layout = QVBoxLayout(directory_group)
        directory_layout.setContentsMargins(6, 12, 6, 6)  # Reduced margins
        directory_layout.setSpacing(4)  # Reduced spacing

        directory_hbox = QHBoxLayout()
        self.select_directory_button = ActionButton("Select Directory",
                                                    tooltip="Choose a directory to scan for Python files")
        self.select_directory_button.clicked.connect(self.select_directory)
        directory_hbox.addWidget(self.select_directory_button)

        self.directory_label = QLabel(f"Directory: {self.selected_directory.as_posix()}")
        self.directory_label.setStyleSheet("font-weight: normal; color: #333333;")
        directory_hbox.addWidget(self.directory_label, 1)

        # Add reload button to directory section
        self.reload_button = ActionButton("Reload", tooltip="Reload files from directory")
        self.reload_button.clicked.connect(self.reload_files)
        directory_hbox.addWidget(self.reload_button)

        directory_layout.addLayout(directory_hbox)
        main_layout.addWidget(directory_group)

        # File management section
        file_management_group = QGroupBox("File Management")
        file_management_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)  # Make height fixed
        file_management_layout = QVBoxLayout(file_management_group)
        file_management_layout.setContentsMargins(6, 12, 6, 6)  # Reduced margins
        file_management_layout.setSpacing(4)  # Reduced spacing

        # Upload files section
        upload_hbox = QHBoxLayout()
        self.upload_button = ActionButton("Upload Code Files", tooltip="Replace all files with newly selected ones")
        self.upload_button.clicked.connect(self.upload_files_replace)
        upload_hbox.addWidget(self.upload_button)

        self.add_more_button = ActionButton("Add More Files", tooltip="Add additional files to the current list")
        self.add_more_button.clicked.connect(self.upload_files_add)
        upload_hbox.addWidget(self.add_more_button)

        file_management_layout.addLayout(upload_hbox)

        # Selection controls
        selection_hbox = QHBoxLayout()
        self.select_all_button = ActionButton("Select All Files", tooltip="Select all files in the list")
        self.select_all_button.clicked.connect(self.select_all_files)
        selection_hbox.addWidget(self.select_all_button)

        self.unselect_all_button = ActionButton("Unselect All Files", tooltip="Unselect all files in the list")
        self.unselect_all_button.clicked.connect(self.unselect_all_files)
        selection_hbox.addWidget(self.unselect_all_button)

        self.move_head_button = ActionButton("Move Selected to Top",
                                             tooltip="Move selected files to the beginning of the list")
        self.move_head_button.clicked.connect(self.move_checked_files_to_head)
        selection_hbox.addWidget(self.move_head_button)

        file_management_layout.addLayout(selection_hbox)

        # Copy file paths button
        self.copy_all_paths_button = ActionButton("Copy Selected File Paths",
                                                  tooltip="Copy the paths of selected files to clipboard")
        self.copy_all_paths_button.clicked.connect(self.copy_all_file_paths)
        file_management_layout.addWidget(self.copy_all_paths_button)

        main_layout.addWidget(file_management_group)

        # Create a splitter for the main content area
        content_splitter = QSplitter(Qt.Vertical)
        content_splitter.setChildrenCollapsible(False)

        # Selected files section
        selected_files_group = QGroupBox("Selected Files")
        selected_files_layout = QVBoxLayout(selected_files_group)
        selected_files_layout.setContentsMargins(6, 12, 6, 6)  # Reduced margins

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(120)  # Reduced from 180 to 120 to give more space to Available Files
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # Always show vertical scrollbar

        self.file_list_widget = QWidget()
        self.file_list_layout = QVBoxLayout(self.file_list_widget)
        self.file_list_layout.setSpacing(1)  # Reduced from 2 to 1
        self.file_list_layout.setContentsMargins(4, 4, 4, 4)  # Reduced margins
        self.scroll_area.setWidget(self.file_list_widget)

        selected_files_layout.addWidget(self.scroll_area)

        # Add informational label
        info_label = QLabel("Right-click on a file for more options")
        info_label.setStyleSheet("color: #666666; font-style: italic;")
        info_label.setAlignment(Qt.AlignRight)
        selected_files_layout.addWidget(info_label)

        content_splitter.addWidget(selected_files_group)

        # Directory files section
        directory_files_group = QGroupBox("Available Files")
        directory_files_layout = QVBoxLayout(directory_files_group)
        directory_files_layout.setContentsMargins(6, 12, 6, 6)  # Reduced margins from 8 to 6

        # Add "Add Selected to List" button at the top
        self.move_ahead_button_tabbar = ActionButton("Add Selected to List",
                                                     tooltip="Add selected files from current tab to the main list")
        self.move_ahead_button_tabbar.clicked.connect(self.add_selected_files_from_current_tab)
        directory_files_layout.addWidget(self.move_ahead_button_tabbar)

        self.filter_tabs = QTabWidget()
        self.filter_tabs.setDocumentMode(True)
        self.filter_tabs.setTabPosition(QTabWidget.North)
        self.filter_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #c0c0c0;
                border-radius: 3px;
                padding: 3px;
            }
            QTabBar::tab {
                background: #f0f0f0;
                border: 1px solid #c0c0c0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 4px 8px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom: none;
            }
            QTabBar::tab:hover {
                background: #e0f0ff;
            }
        """)

        self.filter_tabs_scroll = QScrollArea()
        self.filter_tabs_scroll.setWidgetResizable(True)
        self.filter_tabs_scroll.setMinimumHeight(500)  # Increased from 450 to 500 for more visible files
        self.filter_tabs_scroll.setWidget(self.filter_tabs)
        self.filter_tabs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # Always show vertical scrollbar

        directory_files_layout.addWidget(self.filter_tabs_scroll)

        content_splitter.addWidget(directory_files_group)

        # Set initial sizes for the splitter - give more space to available files section
        content_splitter.setSizes([120, 580])  # Adjusted ratio to give even more space to Available Files

        main_layout.addWidget(content_splitter, 1)

        # Output section - MODIFIED to ensure buttons remain visible when window is resized
        output_group = QGroupBox("Output Actions")
        output_group.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)  # Make height fixed
        output_layout = QVBoxLayout(output_group)
        output_layout.setContentsMargins(6, 12, 6, 6)  # Reduced margins
        output_layout.setSpacing(4)  # Reduced spacing

        # Create a horizontal layout that won't collapse when window is minimized
        copy_hbox = QHBoxLayout()
        copy_hbox.setContentsMargins(0, 0, 0, 0)
        copy_hbox.setSpacing(4)

        # Copy combined code button - MODIFIED to ensure visibility
        self.copy_button = ActionButton("Copy Combined Code", tooltip="Combine selected files and copy to clipboard")
        self.copy_button.clicked.connect(self.copy_combined_code)
        self.copy_button.setStyleSheet("""
            QPushButton {
                background-color: #e0f0e0;
                font-weight: bold;
                min-width: 200px;  /* Increased from 150px to 200px */
            }
            QPushButton:hover {
                background-color: #c0e0c0;
            }
        """)
        self.copy_button.setMinimumHeight(32)  # Increased from 30 to 32
        self.copy_button.setMinimumWidth(180)  # Added explicit minimum width
        self.copy_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)  # Ensure fixed height
        copy_hbox.addWidget(self.copy_button)

        self.copy_combined_label = StatusLabel()
        copy_hbox.addWidget(self.copy_combined_label)

        # Copy files button - MODIFIED to ensure visibility
        self.copy_file_button = ActionButton("Copy Files to Clipboard", tooltip="Copy selected files to clipboard")
        self.copy_file_button.clicked.connect(self.copy_selected_files)
        self.copy_file_button.setStyleSheet("""
            QPushButton {
                min-width: 200px;  /* Increased from 150px to 200px */
            }
        """)
        self.copy_file_button.setMinimumHeight(32)  # Increased from 30 to 32
        self.copy_file_button.setMinimumWidth(180)  # Added explicit minimum width
        self.copy_file_button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)  # Ensure fixed height
        copy_hbox.addWidget(self.copy_file_button)

        self.copy_file_label = StatusLabel()
        copy_hbox.addWidget(self.copy_file_label)

        output_layout.addLayout(copy_hbox)


        # Ensure Output Actions group has a fixed height and doesn't collapse
        output_group.setMinimumHeight(80)
        output_group.setMaximumHeight(100)
        main_layout.addWidget(output_group)

    def select_directory(self):
        """Open a dialog to select a directory"""
        chosen_dir = QFileDialog.getExistingDirectory(self, "Select Directory", str(self.selected_directory))
        if chosen_dir:
            self.selected_directory = Path(chosen_dir)
            self.settings.setValue("selected_directory", chosen_dir)
            self.directory_label.setText(f"Directory: {chosen_dir}")
            self.filter_and_scan_file_paths()
            self.status_bar.showMessage(f"Directory changed to: {chosen_dir}", 3000)

    def build_directory_tabs(self, all_files_grouped):
        """Build tabs for each directory containing files"""
        # Clear existing tabs
        while self.filter_tabs.count() > 0:
            tab = self.filter_tabs.widget(0)
            self.filter_tabs.removeTab(0)
            tab.deleteLater()

        self.directory_tabs.clear()
        self.tab_file_checkboxes.clear()

        # Create tabs for each directory
        for dir_key, files in sorted(all_files_grouped.items()):
            tab_widget = QWidget()
            tab_layout = QVBoxLayout(tab_widget)
            tab_layout.setSpacing(1)  # Reduced from 2 to 1
            tab_layout.setContentsMargins(2, 2, 2, 2)  # Reduced from 5,5,5,5 to 2,2,2,2

            # Create a scroll area for file checkboxes to make them scrollable
            files_scroll_area = QScrollArea()
            files_scroll_area.setWidgetResizable(True)
            files_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)  # Always show vertical scrollbar
            files_content_widget = QWidget()
            files_content_layout = QVBoxLayout(files_content_widget)
            files_content_layout.setSpacing(0)  # Reduced from 2 to 0 to make it more compact
            files_content_layout.setContentsMargins(0, 0, 0, 0)

            # Add file checkboxes
            self.tab_file_checkboxes[dir_key] = []
            for rel_path, abs_path in files:
                hbox = QHBoxLayout()
                hbox.setSpacing(2)  # Reduced from 4 to 2
                hbox.setContentsMargins(1, 0, 1, 0)  # Reduced from 2,0,2,0 to 1,0,1,0

                # Create checkbox with file information
                checkbox = FileCheckBox(rel_path, abs_path, self)

                # Try to get line count for display
                try:
                    line_count = sum(1 for _ in open(abs_path, 'r', encoding='utf-8'))
                    rel_path_with_count = f"{rel_path} ({line_count} lines)"
                    checkbox.setText(rel_path_with_count)
                except:
                    pass

                hbox.addWidget(checkbox)
                self.tab_file_checkboxes[dir_key].append((checkbox, Path(abs_path)))
                hbox.addStretch()

                file_item_widget = QWidget()
                file_item_widget.setFixedHeight(20)  # Reduced from 24 to 20
                file_item_widget.setLayout(hbox)
                files_content_layout.addWidget(file_item_widget)

            # Add stretch to push all items to the top
            files_content_layout.addStretch()

            # Set up scroll area
            files_scroll_area.setWidget(files_content_widget)
            tab_layout.addWidget(files_scroll_area, 1)  # Give it a stretch factor of 1

            self.filter_tabs.addTab(tab_widget, dir_key)

        # If no tabs were created, add an empty tab
        if self.filter_tabs.count() == 0:
            empty_tab = QWidget()
            empty_layout = QVBoxLayout(empty_tab)
            empty_label = QLabel("No Python files found in the selected directory")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #888888; font-style: italic;")
            empty_layout.addWidget(empty_label)
            empty_layout.addStretch()
            self.filter_tabs.addTab(empty_tab, "No Files")

    def select_all_in_tab(self, dir_key):
        """Select all files in a specific tab"""
        if dir_key not in self.tab_file_checkboxes:
            return

        for (checkbox, _) in self.tab_file_checkboxes[dir_key]:
            checkbox.setChecked(True)

    def deselect_all_in_tab(self, dir_key):
        """Deselect all files in a specific tab"""
        if dir_key not in self.tab_file_checkboxes:
            return

        for (checkbox, _) in self.tab_file_checkboxes[dir_key]:
            checkbox.setChecked(False)

    def add_selected_files_from_current_tab(self):
        """Add selected files from the current tab to the main list"""
        current_index = self.filter_tabs.currentIndex()
        if current_index < 0:
            return

        dir_key = self.filter_tabs.tabText(current_index)
        self.add_selected_files_from_tab(dir_key)

    def add_selected_files_from_tab(self, dir_key):
        """Add selected files from a specific tab to the main list"""
        if dir_key not in self.tab_file_checkboxes:
            return

        any_checked = False
        newly_added = []
        existing_names = {fp.name for fp in self.file_paths}

        for (checkbox, file_path) in self.tab_file_checkboxes[dir_key]:
            if checkbox.isChecked():
                any_checked = True
                if file_path.name not in existing_names:
                    self.file_paths.append(file_path)
                    existing_names.add(file_path.name)
                    newly_added.append(file_path)
                    self.check_file(file_path)

        if not any_checked:
            self.status_bar.showMessage(f"No files selected from '{dir_key}'", 3000)
            return

        if newly_added:
            self.settings.setValue("file_paths", [fp.as_posix() for fp in self.file_paths])
            self.display_filenames()
            self.status_bar.showMessage(f"Added {len(newly_added)} new files from '{dir_key}'", 3000)
        else:
            self.status_bar.showMessage(f"All selected files from '{dir_key}' were already in the list", 3000)

    def filter_and_scan_file_paths(self):
        """Filter the file paths and scan for new files"""
        allowed_extensions = {'.py'}
        excluded_filenames = {'__init__.py', 'Codehelp.py', 'analysis_depend.py'}

        # Filter out invalid files
        filtered_file_paths = [
            fp for fp in self.file_paths
            if fp.suffix.lower() in allowed_extensions and fp.name not in excluded_filenames
        ]

        # Remove duplicates (by filename)
        unique_file_paths = []
        seen_file_names = set()

        for fp in filtered_file_paths:
            if fp.name not in seen_file_names:
                unique_file_paths.append(fp)
                seen_file_names.add(fp.name)

        self.file_paths = unique_file_paths
        self.settings.setValue("file_paths", [fp.as_posix() for fp in self.file_paths])

        # Scan directory and display files
        self.scan_and_display_directory_files()

        # Display the file list
        self.display_filenames()

    def scan_and_display_directory_files(self):
        """Scan the selected directory for Python files and display them in tabs"""
        allowed_extensions = {'.py'}
        excluded_filenames = {'__init__.py', 'Codehelp.py', 'analysis_depend.py'}
        excluded_dirs = {'__pycache__', '.git', '.venv', 'venv', '.idea', '.vscode'}

        script_dir = self.selected_directory
        self.directory_label.setText(f"Directory: {script_dir.as_posix()}")

        # Group files by directory
        all_files_grouped = {}

        for root, dirs, files in os.walk(script_dir):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in excluded_dirs]

            root_path = Path(root)

            for file in files:
                file_path = root_path / file

                # Check if it's a Python file and not excluded
                if file_path.suffix.lower() in allowed_extensions and file_path.name not in excluded_filenames:
                    try:
                        # Get relative path for display
                        rel = file_path.relative_to(script_dir).as_posix()
                    except ValueError:
                        rel = file_path.as_posix()

                    try:
                        # Get directory name for tab organization
                        dir_rel = file_path.parent.relative_to(script_dir).as_posix()
                        if dir_rel == ".":
                            dir_rel = "(top-level)"
                    except ValueError:
                        dir_rel = file_path.parent.as_posix()

                    # Add to grouped files
                    if dir_rel not in all_files_grouped:
                        all_files_grouped[dir_rel] = []

                    all_files_grouped[dir_rel].append((rel, file_path.as_posix()))

        # Build tabs from grouped files
        self.build_directory_tabs(all_files_grouped)

    def reload_files(self):
        """Reload files from the selected directory"""
        self.filter_and_scan_file_paths()
        self.status_bar.showMessage("Directory has been rescanned and file list updated", 3000)

    def upload_files_replace(self):
        """Replace all files with newly selected files"""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("Python Files (*.py)")

        if file_dialog.exec():
            new_file_paths = [Path(fp) for fp in file_dialog.selectedFiles()]

            if not new_file_paths:
                self.status_bar.showMessage("No files were selected", 3000)
                return

            allowed_extensions = {'.py'}
            excluded_filenames = {'__init__.py', 'Codehelp.py', 'analysis_depend.py'}

            # Filter and remove duplicates
            filtered_file_paths = [
                fp for fp in new_file_paths
                if fp.suffix.lower() in allowed_extensions and fp.name not in excluded_filenames
            ]

            unique_file_paths = []
            seen_file_names = set()

            for fp in filtered_file_paths:
                if fp.name not in seen_file_names:
                    unique_file_paths.append(fp)
                    seen_file_names.add(fp.name)

            # Replace files and update state
            self.file_paths = unique_file_paths
            self.checked_file_paths = set(unique_file_paths)
            self.settings.setValue("file_paths", [fp.as_posix() for fp in self.file_paths])

            # Update display
            self.display_filenames()
            self.status_bar.showMessage(f"Replaced files with {len(unique_file_paths)} new files", 3000)

    def upload_files_add(self):
        """Add additional files to the current list"""
        file_dialog = QFileDialog(self)
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("Python Files (*.py)")

        if file_dialog.exec():
            new_file_paths = [Path(fp) for fp in file_dialog.selectedFiles()]

            if not new_file_paths:
                self.status_bar.showMessage("No files were selected", 3000)
                return

            allowed_extensions = {'.py'}
            excluded_filenames = {'__init__.py', 'Codehelp.py', 'analysis_depend.py'}

            # Filter and check for existing files
            filtered_file_paths = [
                fp for fp in new_file_paths
                if fp.suffix.lower() in allowed_extensions and fp.name not in excluded_filenames
            ]

            existing_file_names = {fp.name for fp in self.file_paths}
            added_files = []
            skipped_files = []

            for file_path in filtered_file_paths:
                if file_path.name not in existing_file_names:
                    self.file_paths.append(file_path)
                    existing_file_names.add(file_path.name)
                    added_files.append(file_path)
                    self.check_file(file_path)
                else:
                    skipped_files.append(file_path)

            # Update state and display
            self.settings.setValue("file_paths", [fp.as_posix() for fp in self.file_paths])
            self.display_filenames()

            # Show status message
            if added_files:
                self.status_bar.showMessage(f"Added {len(added_files)} new files", 3000)

            if skipped_files:
                skipped_names = ", ".join([fp.name for fp in skipped_files[:5]])
                if len(skipped_files) > 5:
                    skipped_names += f" and {len(skipped_files) - 5} more"

                warning_msg = f"Skipped {len(skipped_files)} files with duplicate names: {skipped_names}"
                QMessageBox.warning(self, "Duplicate Files Skipped", warning_msg)

    def display_filenames(self):
        """Display the list of selected files"""
        # Clear existing widgets
        for i in reversed(range(self.file_list_layout.count())):
            widget_to_remove = self.file_list_layout.itemAt(i).widget()
            if widget_to_remove is not None:
                self.file_list_layout.removeWidget(widget_to_remove)
                widget_to_remove.deleteLater()

        self.checkboxes = []
        self.operation_labels = {}
        script_dir = self.selected_directory

        # Handle empty file list
        if not self.file_paths:
            empty_label = QLabel("No files selected. Add files from the tabs below or use the 'Upload' buttons.")
            empty_label.setAlignment(Qt.AlignCenter)
            empty_label.setStyleSheet("color: #888888; font-style: italic; padding: 20px;")
            self.file_list_layout.addWidget(empty_label)
            self.update_select_all_state()
            return

        # Add file items
        for file_path in self.file_paths:
            # Create container widget for file row
            file_item_widget = QWidget()
            file_item_widget.setFixedHeight(24)  # Reduced from 28 to 24
            file_item_widget.setStyleSheet("""
                QWidget {
                    border-bottom: 1px solid #e0e0e0;
                    background-color: transparent;
                }
                QWidget:hover {
                    background-color: #f8f8f8;
                }
            """)

            # Create layout for file row
            hbox = QHBoxLayout(file_item_widget)
            hbox.setSpacing(2)  # Reduced from 4 to 2
            hbox.setContentsMargins(1, 0, 1, 0)  # Reduced vertical margins

            # Get line count for display
            try:
                with file_path.open("r", encoding="utf-8") as file:
                    line_count = sum(1 for _ in file)
            except Exception:
                line_count = "N/A"

            # Create display text
            display_text = self.relative_or_absolute(file_path, script_dir)
            display_text_with_count = f"{display_text} ({line_count} lines)"

            # Create checkbox
            checkbox = FileCheckBox(display_text_with_count, file_path, self)
            checkbox.setChecked(file_path in self.checked_file_paths)
            checkbox.stateChanged.connect(self.checkbox_state_changed)
            checkbox.rightClicked.connect(self.highlight_checkbox)
            self.checkboxes.append((checkbox, file_path))
            hbox.addWidget(checkbox, 1)

            # Create action buttons
            button_layout = QHBoxLayout()
            button_layout.setSpacing(1)  # Reduced from 2 to 1

            # Copy button
            copy_button = ActionButton("Copy", tooltip=f"Copy the content of {file_path.name}")
            copy_button.setFixedWidth(50)  # Reduced from 55 to 50
            copy_button.clicked.connect(self.create_copy_function(file_path))
            button_layout.addWidget(copy_button)

            # Copy status label
            copy_label = StatusLabel()
            button_layout.addWidget(copy_label)

            # Paste button
            paste_button = ActionButton("Paste", tooltip=f"Paste clipboard content to {file_path.name}")
            paste_button.setFixedWidth(50)  # Reduced from 55 to 50
            paste_button.clicked.connect(self.create_paste_function(file_path))
            button_layout.addWidget(paste_button)

            # Paste status label
            paste_label = StatusLabel()
            button_layout.addWidget(paste_label)

            # Revert button
            revert_button = ActionButton("Revert", tooltip=f"Revert {file_path.name} to previous version")
            revert_button.setFixedWidth(50)  # Reduced from 55 to 50
            revert_button.clicked.connect(self.create_revert_function(file_path))
            button_layout.addWidget(revert_button)

            # Revert status label
            revert_label = StatusLabel()
            button_layout.addWidget(revert_label)

            # Remove button
            remove_button = ActionButton("Remove", tooltip=f"Remove {file_path.name} from the list")
            remove_button.setFixedWidth(50)  # Reduced from 55 to 50
            remove_button.clicked.connect(self.create_remove_function(file_path))
            button_layout.addWidget(remove_button)

            hbox.addLayout(button_layout)

            # Add to layout
            self.file_list_layout.addWidget(file_item_widget)

            # Store labels for status updates
            self.operation_labels[file_path] = {
                'copy': copy_label,
                'paste': paste_label,
                'revert': revert_label
            }

        # Add stretcher at the end
        self.file_list_layout.addStretch()

        # Update status
        self.update_select_all_state()
        if self.file_paths:
            self.directory_label.setText(f"Directory: {script_dir.as_posix()}")
        else:
            self.directory_label.setText("Directory: Not Selected")

    def checkbox_state_changed(self, state):
        """Handle checkbox state changes"""
        checkbox = self.sender()
        if not isinstance(checkbox, FileCheckBox):
            return

        file_path = checkbox.file_path

        if state == Qt.Checked:
            self.check_file(file_path)
        else:
            self.uncheck_file(file_path)

        self.update_select_all_state()

    def check_file(self, file_path):
        """Mark a file as checked"""
        self.checked_file_paths.add(file_path)

    def uncheck_file(self, file_path):
        """Mark a file as unchecked"""
        self.checked_file_paths.discard(file_path)

    def relative_or_absolute(self, file_path, script_dir):
        """Get a relative path if possible, otherwise absolute"""
        try:
            return file_path.relative_to(script_dir).as_posix()
        except ValueError:
            return file_path.as_posix()

    def highlight_checkbox(self, clicked_checkbox):
        """Highlight the selected checkbox"""
        # Reset previous highlight
        if self.highlighted_checkbox and self.highlighted_checkbox != clicked_checkbox:
            self.highlighted_checkbox.setStyleSheet("""
                QCheckBox {
                    spacing: 4px;
                    margin: 1px;
                    padding: 1px;
                    font-family: Arial;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                    margin: 1px;
                }
                QCheckBox:hover {
                    background-color: #e0f0ff;
                    border-radius: 3px;
                }
            """)

        # Set new highlight
        clicked_checkbox.setStyleSheet("""
            QCheckBox {
                spacing: 4px;
                margin: 1px;
                padding: 1px;
                font-family: Arial;
                background-color: #d0e8ff;
                border-radius: 3px;
            }
            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                margin: 1px;
            }
            QCheckBox:hover {
                background-color: #c0e0ff;
            }
        """)

        self.highlighted_checkbox = clicked_checkbox

    def create_remove_function(self, file_path):
        """Create a function to remove a specific file"""
        return lambda: self.remove_file(file_path)

    def remove_file(self, file_path):
        """Remove a file from the list"""
        if file_path in self.file_paths:
            self.file_paths.remove(file_path)
            self.uncheck_file(file_path)
            self.settings.setValue("file_paths", [fp.as_posix() for fp in self.file_paths])
            self.display_filenames()
            self.status_bar.showMessage(f"Removed {file_path.name} from the list", 3000)

    def create_copy_function(self, file_path):
        """Create a function to copy a specific file's content"""
        return lambda: self.copy_file_code(file_path)

    def create_paste_function(self, file_path):
        """Create a function to paste to a specific file"""
        return lambda: self.paste_file_code(file_path)

    def create_revert_function(self, file_path):
        """Create a function to revert a specific file"""
        return lambda: self.revert_file_code(file_path)

    def copy_file_code(self, file_path):
        """Copy a file's content to clipboard"""
        try:
            with file_path.open("r", encoding="utf-8") as file:
                file_code = file.readlines()

            script_dir = self.selected_directory

            try:
                relative_path = file_path.relative_to(script_dir).as_posix()
            except ValueError:
                relative_path = file_path.as_posix()

            file_identifier = f"# {relative_path}"

            # Format content with file identifier
            if file_code:
                first_line = file_code[0].strip()
                if first_line != file_identifier:
                    clipboard_content = f"{file_identifier}\n" + "".join(file_code)
                else:
                    clipboard_content = "".join(file_code)
            else:
                clipboard_content = f"{file_identifier}\n"

            # Copy to clipboard
            QApplication.clipboard().setText(clipboard_content)

            # Save current version for potential revert
            self.save_current_version(file_path)

            # Update status
            if file_path in self.operation_labels and 'copy' in self.operation_labels[file_path]:
                label = self.operation_labels[file_path]['copy']
                label.show_success()

            self.status_bar.showMessage(f"Copied {file_path.name} to clipboard", 3000)

        except UnicodeDecodeError:
            error_msg = f"Failed to copy file '{file_path.name}': Not a valid text file"
            self.status_bar.showMessage(error_msg, 5000)

            if file_path in self.operation_labels and 'copy' in self.operation_labels[file_path]:
                label = self.operation_labels[file_path]['copy']
                label.show_failure()

            QMessageBox.critical(self, "Error", error_msg)

        except Exception as e:
            error_msg = f"Failed to copy file '{file_path.name}': {str(e)}"
            self.status_bar.showMessage(error_msg, 5000)

            if file_path in self.operation_labels and 'copy' in self.operation_labels[file_path]:
                label = self.operation_labels[file_path]['copy']
                label.show_failure()

            QMessageBox.critical(self, "Error", error_msg)

    def paste_file_code(self, file_path):
        """Paste clipboard content to a file"""
        clipboard_text = QApplication.clipboard().text()

        if clipboard_text:
            try:
                lines = clipboard_text.splitlines()

                if not lines:
                    warning_msg = "Clipboard is empty. Please copy some text first."
                    self.status_bar.showMessage(warning_msg, 3000)

                    if file_path in self.operation_labels and 'paste' in self.operation_labels[file_path]:
                        label = self.operation_labels[file_path]['paste']
                        label.show_warning()

                    QMessageBox.warning(self, "Warning", warning_msg)
                    return

                # Determine the correct identifier for the file
                script_dir = self.selected_directory
                try:
                    relative_path = file_path.relative_to(script_dir).as_posix()
                except ValueError:
                    relative_path = file_path.as_posix()

                expected_first_line = f"# {relative_path}"
                first_line = lines[0].strip()

                # Format content with correct identifier
                if first_line == expected_first_line:
                    content_to_write = clipboard_text
                else:
                    if file_path.exists():
                        existing_lines = file_path.read_text(encoding="utf-8").splitlines()
                        if existing_lines:
                            existing_first_line = existing_lines[0].strip()
                            if existing_first_line == expected_first_line:
                                remaining_content = "\n".join(lines)
                                content_to_write = f"{existing_first_line}\n{remaining_content}"
                            else:
                                content_to_write = f"{expected_first_line}\n{clipboard_text}"
                        else:
                            content_to_write = f"{expected_first_line}\n{clipboard_text}"
                    else:
                        content_to_write = f"{expected_first_line}\n{clipboard_text}"

                # Save current version for potential revert
                self.save_current_version(file_path)

                # Write content to file
                file_path.write_text(content_to_write, encoding="utf-8")

                # Update status
                if file_path in self.operation_labels and 'paste' in self.operation_labels[file_path]:
                    label = self.operation_labels[file_path]['paste']
                    label.show_success()

                self.update_line_count(file_path)
                self.status_bar.showMessage(f"Pasted content to {file_path.name}", 3000)

            except Exception as e:
                error_msg = f"Failed to paste into file '{file_path.name}': {str(e)}"
                self.status_bar.showMessage(error_msg, 5000)

                if file_path in self.operation_labels and 'paste' in self.operation_labels[file_path]:
                    label = self.operation_labels[file_path]['paste']
                    label.show_failure()

                QMessageBox.critical(self, "Error", error_msg)
        else:
            warning_msg = "Clipboard is empty. Please copy some text first."
            self.status_bar.showMessage(warning_msg, 3000)

            if file_path in self.operation_labels and 'paste' in self.operation_labels[file_path]:
                label = self.operation_labels[file_path]['paste']
                label.show_warning()

            QMessageBox.warning(self, "Warning", warning_msg)

    def save_current_version(self, file_path):
        """Save the current version of a file for potential revert"""
        try:
            current_content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            error_msg = f"Failed to read file '{file_path.name}': {str(e)}"
            self.status_bar.showMessage(error_msg, 5000)
            QMessageBox.critical(self, "Error", error_msg)
            return

        # Initialize or update version history
        if file_path not in self.previous_versions:
            self.previous_versions[file_path] = []

        self.previous_versions[file_path].append(current_content)

        # Limit history size
        if len(self.previous_versions[file_path]) > 5:  # Increased from 3 to 5
            self.previous_versions[file_path].pop(0)

    def revert_file_code(self, file_path):
        """Revert a file to its previous version"""
        if file_path in self.previous_versions and self.previous_versions[file_path]:
            try:
                previous_code = self.previous_versions[file_path].pop()
                file_path.write_text(previous_code, encoding="utf-8")

                # Update status
                if file_path in self.operation_labels and 'revert' in self.operation_labels[file_path]:
                    label = self.operation_labels[file_path]['revert']
                    label.show_success()

                self.update_line_count(file_path)
                self.status_bar.showMessage(f"Reverted {file_path.name} to previous version", 3000)

            except Exception as e:
                error_msg = f"Failed to revert file '{file_path.name}': {str(e)}"
                self.status_bar.showMessage(error_msg, 5000)

                if file_path in self.operation_labels and 'revert' in self.operation_labels[file_path]:
                    label = self.operation_labels[file_path]['revert']
                    label.show_failure()

                QMessageBox.critical(self, "Error", error_msg)
        else:
            warning_msg = f"No previous versions available for file '{file_path.name}'"
            self.status_bar.showMessage(warning_msg, 3000)

            if file_path in self.operation_labels and 'revert' in self.operation_labels[file_path]:
                label = self.operation_labels[file_path]['revert']
                label.show_warning()

            QMessageBox.warning(self, "Warning", warning_msg)

    def update_select_all_state(self):
        """Update the state of select/deselect all buttons"""
        if not self.checkboxes:
            self.select_all_button.setEnabled(False)
            self.unselect_all_button.setEnabled(False)
            return

        all_checked = all(cb.isChecked() for cb, _ in self.checkboxes)
        any_checked = any(cb.isChecked() for cb, _ in self.checkboxes)

        self.select_all_button.setEnabled(not all_checked)
        self.unselect_all_button.setEnabled(any_checked)

    def select_all_files(self):
        """Select all files in the list"""
        for checkbox, fp in self.checkboxes:
            checkbox.setChecked(True)
            self.check_file(fp)

        self.update_select_all_state()
        self.status_bar.showMessage("Selected all files", 3000)

    def unselect_all_files(self):
        """Unselect all files in the list"""
        for checkbox, fp in self.checkboxes:
            checkbox.setChecked(False)
            self.uncheck_file(fp)

        self.update_select_all_state()
        self.status_bar.showMessage("Deselected all files", 3000)

    def move_checked_files_to_head(self):
        """Move checked files to the top of the list"""
        checked_files = [fp for cb, fp in self.checkboxes if cb.isChecked()]
        unchecked_files = [fp for cb, fp in self.checkboxes if not cb.isChecked()]

        if not checked_files:
            self.status_bar.showMessage("No files selected to move", 3000)
            return

        self.file_paths = checked_files + unchecked_files
        self.settings.setValue("file_paths", [fp.as_posix() for fp in self.file_paths])
        self.display_filenames()

        self.status_bar.showMessage(f"Moved {len(checked_files)} selected files to the top", 3000)

    def combine_code(self):
        """Combine code from selected files"""
        combined_code = ""
        script_dir = self.selected_directory
        selected_files = [fp for cb, fp in self.checkboxes if cb.isChecked()]

        if not selected_files:
            return ""

        for file_path in selected_files:
            if not file_path.exists():
                warning_msg = f"The file '{file_path.name}' was not found. Please re-upload."
                self.status_bar.showMessage(warning_msg, 5000)
                QMessageBox.warning(self, "File Not Found", warning_msg)
                continue

            try:
                with file_path.open("r", encoding="utf-8") as file:
                    lines = file.readlines()

                # Get relative path for file identifier
                try:
                    relative_dir = file_path.parent.relative_to(script_dir).as_posix()
                except ValueError:
                    relative_dir = file_path.parent.as_posix()

                file_name = file_path.name

                # Create file identifier
                if relative_dir in ('', '.', '(top-level)'):
                    file_identifier = f"# {file_name}"
                else:
                    file_identifier = f"# {relative_dir}/{file_name}"

                # Add file identifier if not already present
                if lines:
                    first_line = lines[0].strip()
                    if first_line != file_identifier.strip():
                        lines.insert(0, f"{file_identifier}\n")
                else:
                    lines.insert(0, f"{file_identifier}\n")

                # Add file content to combined code
                file_content = ''.join(lines)
                combined_code += file_content + "\n\n"

            except UnicodeDecodeError:
                warning_msg = f"Skipped binary file '{file_path.name}'. Cannot decode as text."
                self.status_bar.showMessage(warning_msg, 5000)
                QMessageBox.warning(self, "Warning", warning_msg)

            except Exception as e:
                error_msg = f"Failed to read file '{file_path.name}': {str(e)}"
                self.status_bar.showMessage(error_msg, 5000)
                QMessageBox.critical(self, "Error", error_msg)

        return combined_code

    def copy_combined_code(self):
        """Combine selected files' code and copy to clipboard"""
        combined_code = self.combine_code()

        if combined_code.strip():
            QApplication.clipboard().setText(combined_code)
            self.copy_combined_label.show_success()

            # Count files and lines
            selected_files = [fp for cb, fp in self.checkboxes if cb.isChecked()]
            line_count = combined_code.count('\n')

            self.status_bar.showMessage(
                f"Copied combined code from {len(selected_files)} files ({line_count} lines) to clipboard",
                3000
            )
        else:
            warning_msg = "No files selected to combine"
            self.status_bar.showMessage(warning_msg, 3000)
            self.copy_combined_label.show_warning()
            QMessageBox.warning(self, "Warning", warning_msg)

    def copy_all_file_paths(self):
        """Copy selected file paths to clipboard"""
        selected_file_paths = [fp for cb, fp in self.checkboxes if cb.isChecked()]

        if not selected_file_paths:
            warning_msg = "No files selected to copy paths"
            self.status_bar.showMessage(warning_msg, 3000)
            QMessageBox.warning(self, "Warning", warning_msg)
            return

        script_dir = self.selected_directory
        relative_file_info = []

        for file_path in selected_file_paths:
            try:
                relative_path = file_path.relative_to(script_dir).as_posix()
            except ValueError:
                relative_path = file_path.as_posix()

            relative_file_info.append(relative_path)

        all_paths_str = "\n".join(relative_file_info)
        QApplication.clipboard().setText(all_paths_str)

        self.status_bar.showMessage(f"Copied {len(selected_file_paths)} file paths to clipboard", 3000)

    def copy_selected_files(self):
        """Copy selected files to clipboard (as files)"""
        selected_file_paths = [fp for cb, fp in self.checkboxes if cb.isChecked()]

        if not selected_file_paths:
            warning_msg = "No files selected to copy"
            self.status_bar.showMessage(warning_msg, 3000)
            QMessageBox.warning(self, "Warning", warning_msg)
            return

        # Create mime data with file URLs
        mime_data = QMimeData()
        urls = [QUrl.fromLocalFile(fp.as_posix()) for fp in selected_file_paths]
        mime_data.setUrls(urls)
        QApplication.clipboard().setMimeData(mime_data)

        self.copy_file_label.show_success()
        self.status_bar.showMessage(f"Copied {len(selected_file_paths)} files to clipboard", 3000)

    def closeEvent(self, event):
        """Handle application close event"""
        # Save file paths
        self.settings.setValue("file_paths", [fp.as_posix() for fp in self.file_paths])
        event.accept()

    def update_line_count(self, file_path):
        """Update line count in file checkbox label"""
        for checkbox, fp in self.checkboxes:
            if fp == file_path:
                try:
                    with file_path.open("r", encoding="utf-8") as file:
                        line_count = sum(1 for _ in file)
                except Exception:
                    line_count = "N/A"

                display_text = self.relative_or_absolute(file_path, self.selected_directory)
                display_text_with_count = f"{display_text} ({line_count} lines)"
                checkbox.setText(display_text_with_count)
                break


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Apply application-wide stylesheet
    app.setStyleSheet("""
        QToolTip {
            background-color: #ffffdd;
            color: #333333;
            border: 1px solid #cccccc;
            padding: 4px;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #c0c0c0;
            border-radius: 5px;
            margin-top: 8px;
            padding-top: 12px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px 0 4px;
            background-color: #ffffff;
        }
    """)

    window = CodeCombinerApp()
    window.show()
    sys.exit(app.exec())