#!/usr/bin/env python
from openpyxl import load_workbook
from pdb import set_trace as debug
import re
import os
from BeautifulSoup import BeautifulSoup as bs3
import sys

import logging as log
os.chdir(os.path.dirname(os.path.abspath(sys.argv[0])))
log.basicConfig(filename='mailmerge.log',level=log.INFO)

log.info(os.getcwd())
log.info(os.path.abspath(__name__))

from snlmailer import Message
import datetime

from django.template import engines
from django.conf import settings
import django
settings.configure(SILENCED_SYSTEM_CHECKS = ["1_8.W001"])
django.setup()
django_engine = engines['django']
Template = django_engine.from_string

from nameparser import HumanName



from argparse import ArgumentParser
parser = ArgumentParser(description=u"""Send emails based on data in an excel spreadsheet called data.xlsx.  Emails are
sent to the address listed in the 'email' column and data. The email is sent as HTML with a text part autogenerated from
the HTML. Put the HTML in 'template.html. Subject comes from the <title></title> tag in the head of the template.""")

parser.add_argument("-s", "--stylesheet", action="store_true", help="include stylesheet.css in each emails. This may prevent the text part from being automatically generated. ")
ns = parser.parse_args()

if ns.stylesheet:
    try:
        stylesheet = open('stylesheet.css', 'rb').read().decode('utf-8')
    except Exception as e:
        log.info("No stylesheet found.")
        stylesheet = u""
else:
    stylesheet = u""

wb = load_workbook("data.xlsx")
wsname = wb.get_sheet_names()[0]
ws = wb[wsname]

headers = [cell.value for cell in ws.rows[0]]
headers = {header: headers.index(header) for header in headers}

def clean_template(html):
    soup = bs3(html)
    try:
        #Subject might be in the first line of the body.
        Subject = soup.p.text.split("Subject:")[1].strip()
        #Now delete the subject from the template
        soup.p.extract()
    except IndexError:
        #We couldn't find a subject in the tempalte, lets use the name of the parent folder unless it's "mailmerge"
        Subject = os.path.split(os.getcwd())[1]
        if Subject == "mailmerge":
            print("Could not find a Subject. Put a Subject: line as the first line of your template or rename the mailmerge folder to be the subject.")
            sys.exit()

    #Remove meta and style sections of the head
    [meta.extract() for meta in soup('meta')]
    [style.extract() for style in soup('style')]
    htmlTemplate = unicode(soup)
    return(htmlTemplate, Subject)


htmlTemplate = open("template.html").read().decode("utf-8")
htmlTemplate, Subject = clean_template(htmlTemplate)

rownumber = 0
for row in ws.rows[1:]:
    rownumber += 1
    rowDict = {}
    for header in headers:
        rowDict[header] = row[headers[header]].value
    skip = str(rowDict.get("Skiprow", ""))
    if skip and skip.lower() in ["skip", "yes", "true", "1"]:
        print("skipping row {0}.".format(rownumber))
        continue

    #If the spreadsheet defines a new templatename, then re-render the template. Otherwise, use the old one.
    templatefile = rowDict.get("Template")
    if templatefile:
        try:
            htmlTemplate = open(templatefile).read().decode("utf-8")
            htmlTemplate, Subject = clean_template(htmlTemplate)
        except IOError:
            print(u"You have specified a template file {0} that doesn't exist. Exiting...")
            sys.exit(1)


    name = rowDict.get('Name')

    #Guess at the first and last name based on the full name. Put them into the dictionary for use in the template.
    try:
        nameparser = HumanName(name)
        rowDict['Firstname'] = nameparser.first
        rowDict['Lastname'] = nameparser.last
    except TypeError: #Occurs when name None.
        pass


    rowDict['stylesheet'] = stylesheet  #Ususally, this does nothing.
    template = Template(htmlTemplate)
    html = template.render(rowDict)
    msg = Message()
    msg.Subject = Subject

    if name:
        rowDict['To'] = u"{1} <{0}>".format(rowDict['To'], name)

    redirect = rowDict.get('Redirect')
    if redirect:
        rowDict['To'] = redirect
        print("Redirecting to {0}".format(redirect))
    else:
        msg.To = rowDict['To']

    msg.To = rowDict['To']
    msg.From = rowDict.get("From")

    if not msg.To or not msg.From:
        #print("Missing To or From in row {0}".format(rownumber))
        continue

    msg.Html = html
    logmessage = u"{2} : {1} ==> {0}".format(msg.To, msg.Subject, datetime.datetime.now())
    print logmessage
    log.info(logmessage)
    msg.snlSend()
