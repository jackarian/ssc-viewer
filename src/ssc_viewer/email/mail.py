import time

import mailtrap as mt

# create mail object
mail = mt.MailFromTemplate(
    sender=mt.Address(email="ssc-viewer@back-iot.it", name="Mailtrap Test"),
    to=[mt.Address(email="ariannagiacomo@gmail.com")],
    template_uuid="473f855e-8bea-4f40-a54e-40e335b89724",
    template_variables={"station_name": "Sala Grande",
                        "report_name": time.time()},
)

# create client and send
client = mt.MailtrapClient(token="17851966dde377bf23d30c4731f48fe8")
client.send(mail)