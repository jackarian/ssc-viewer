# font sizes are set from the window size in start.py: no font-size here
RED = "#e31100"
GREEN = "#1e8e3e"
ORANGE = "#e67e00"

ROM_NAME_STYLE = """
QLabel {background-color: #fff; color: #e31100}
"""
CLOCK_STYLE = """
QLabel {background-color: #fff; color: #222222}
"""
SECONDARY_STYLE = """
QLabel {background-color: #fff; color: #555555}
"""


def status_style(color):
    return "QLabel {background-color: #fff; color: %s}" % color


def progress_style(color):
    return """
        QProgressBar {
        border: 1px solid #bbbbbb;
        border-radius: 6px;
        background-color: #eeeeee;
        }
        QProgressBar::chunk {
        border-radius: 6px;
        background-color: %s;
        }
        """ % color

INFO_LABEL_STYLE = """
QLabel {background-color: #fff; border: 1px solid black; border-radius: 10px; font-size: 20px; font-weight: bold; color:#e31100;}
"""
PROGRESS_LABEL_STYLE = """ 
        QProgressBar { 
        border: 2px solid grey; 
        border-radius: 5px;  
        text-align: center;
        } 
        QProgressBar::chunk {
        background-color: #e31100;
        width: 20px;
        }
        """

CONNECTION_BUTTON_STYLE = """
        QPushButton {
            border: 2px solid #e31100;
            border-radius: 10px;
            min-width: 80px;
            color: #e31100;
        }

        QPushButton:flat {
            border: 2px solid #e31100;
            background-color: #e31100;
        }
        QPushButton:pressed {
            border: 2px solid #e31100;
            background-color: #f31100;
        }

        QPushButton:default {
            border-color: navy; /* make the default button prominent */
        }        
        """