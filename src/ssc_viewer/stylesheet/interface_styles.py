ROM_NAME_STYLE = """
QLabel {background-color: #fff; font-size: 30px; font-weight: bold; color: #e31100}
"""
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