from plugins.base_plugin import BasePlugin

from PySide6.QtWidgets import QWidget, QMessageBox, QCheckBox, QApplication
from PySide6.QtCore import QTimer

from app_info import APP_INFO

import requests
import os
import subprocess
import tempfile
import sys


class UpdateChecker(BasePlugin):

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_updates)
        self.timer.start(1000 * 60 * 30)
        self.check_updates()

    def check_updates(self):
        latest_version_url = 'https://api.github.com/repos/dbtdsilva/monitor-controller-kvm/releases/latest'
        current_version = APP_INFO.APP_VERSION

        response = requests.get(latest_version_url)

        if response.status_code != 200:
            self.logger.warn(f'Failed to retrieve version to update: {response.text}')
            return

        installer_url = self.retrieve_installer_remote_url(response.json())
        if installer_url is None:
            self.logger.warn(f'Failed to retrieve installer url from response: {response.json()}')
            return

        remote_version = response.json()['tag_name']
        if current_version >= remote_version:
            return

        self.logger.info(f'Application will retrieve user to update version from {current_version} to {remote_version}')
        if not self.update_confirmation():
            return
        self.update_application(installer_url)

    def retrieve_installer_remote_url(self, response):
        if 'assets' not in response:
            return None

        for asset in response['assets']:
            if 'name' not in asset or not asset['name'].endswith('.exe'):
                continue

            if 'browser_download_url' in asset:
                return asset['browser_download_url']
        return None

    def update_confirmation(self):
        # Create a message box
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle('Update Available')
        msg_box.setText('A new update is available. Would you like to install it now?')

        # Add buttons for user response
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

        remember_option_checkbox = QCheckBox('Remember my selection')
        msg_box.setCheckBox(remember_option_checkbox)

        # Show the message box and get the user's response
        response = msg_box.exec()

        remember_selection = remember_option_checkbox.isChecked()
        if remember_selection:
            pass

        return response == QMessageBox.StandardButton.Yes

    def update_application(self, url):
        installer_file, temp_dir = self.download_file_to_temp(url)
        installed = self.run_installer(installer_file)
        temp_dir.cleanup()

        if installed:
            self.close_application_and_run()

    def close_application_and_run(self):
        # TODO: Properly shutdown QtApplication instead of forcing
        sys.exit(0)

    def download_file_to_temp(self, url):
        try:
            # Create a temporary directory
            temp_dir = tempfile.TemporaryDirectory()

            # Create a temporary file within the directory
            temp_file_path = os.path.join(temp_dir.name, os.path.basename(url))

            # Download the file
            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(temp_file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            self.logger.info(f'Downloaded file saved as: {temp_file_path}')
            return temp_file_path, temp_dir

        except Exception as e:
            self.logger.info(f'An error occurred while downloading the file: {e}')
            return None, None

    def run_installer(self, installer_file):
        try:
            if not installer_file or not os.path.exists(installer_file):
                self.logger.error(f'Installer not found at: {installer_file}')
                return False

            result = subprocess.run([installer_file, '/silent'], check=True)

            if result.returncode != 0:
                self.logger.error(f'Installer failed with return code: {result.returncode}')
                return False

            self.logger.info('Installer successfully updated application')
            return True

        except subprocess.CalledProcessError as e:
            self.logger.error('An error occurred while running the installer', e)
            return False

        except Exception as e:
            self.logger.error('An unexpected error occurred', e)
            return False