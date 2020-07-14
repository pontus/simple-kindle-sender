#!/usr/bin/env python3

import dbm
import configparser
import sys
import os
import sys
import json
import weasyprint
import time
import pocket
import requests
import reportlab.pdfgen.canvas
import reportlab
import reportlab.lib.styles
import reportlab.platypus
import pdfrw
import io
import pdfkit
import email
import email.mime
import email.mime.application
import email.message
import email.headerregistry
import smtplib
import subprocess
import random

cfg = configparser.ConfigParser()

consumerkey = None
token = None
mailserver = None
mailport = None
sender = None
auth = False
ssl = False
starttls = True
smtpuser = None
smtpass = ''

for cfgfile in ('%s/.simple-kindle-sender.conf' % os.environ['HOME'],):
    try:
        cfg.read(cfgfile)
        consumerkey = cfg['pocket'].get('consumerkey')
        token =  cfg['pocket'].get('token')

        sender = cfg['kindle'].get('sender')
        recipient = cfg['kindle'].get('kindleaddress')

        ssl = cfg['smtp'].getboolean('ssl')
        starttls = cfg['smtp'].getboolean('starttls')
        auth = cfg['smtp'].getboolean('auth')
        
        mailserver = cfg['smtp'].get('server')
        mailport = cfg['smtp'].getint('port')

        if auth:
            smtpuser =  cfg['smtp'].get('username')
            smtppass =  cfg['smtp'].get('password')
            
        break
    except Exception as e:
        print(e)
        pass

if not recipient:
    print("Missing configuration kindle->kindleaddress")
    raise SystemExit

if not sender:
    print("Missing configuration kindle->sender")
    raise SystemExit

if not consumerkey:
    print("Missing configuration pocket->consumerkey")
    raise SystemExit

if not token:
    print("Missing configuration pocket->token")
    raise SystemExit


def get_w3m_cookies():
    cookies = requests.cookies.RequestsCookieJar()
    try:
        f = open("%s/.w3m/cookie" % os.environ['HOME'])
        for p in f.readlines():
            l = p.split()
            if l[0][:22] == 'https://getpocket.com/':
                cookies.set(l[1],l[2], domain='getpocket.com')
    except Exception as e:
        print(e)
    return cookies
            


def my_fetcher(url):

    if url.startswith('https://getpocket.com'):
        r = requests.get(url, cookies = cookies)
        return r.text
    else:
        return weasyprint.default_url_fetcher(url)

def file_to_mail(content, sender, recipient, title):
    m = email.message.EmailMessage()
    m['From'] = email.headerregistry.Address(sender, sender)
    m['To'] = email.headerregistry.Address(recipient, recipient)
    m['Subject'] = 'CONVERT'
    m.set_type('text/plain')
    m.set_content('CONVERT')
    m.make_mixed()
    att = email.mime.application.MIMEApplication(content)
    att.set_type('application/pdf')
    att.add_header('Content-Disposition', 'attachment', filename=title)
    m.attach(att)

    return m

def send_mail(content, sender, recipient):
    if mailserver:
        s = None
        if ssl:
            s = smtplib.SMTP_SSL(host = mailserver, port = mailport)
        else:
            s = smtplib.SMTP(host = mailserver, port = mailport)

        if not ssl and starttls:
            s.starttls()

        if auth and smtpuser:
            s.login(smtpuser, smtppass)

        print("Sending mail to %s from %s" % (recipient, sender)) 
        s.sendmail(sender, recipient, content)
        s.quit()
    else:
        print("Sending through sendmail")
        s = subprocess.Popen(('/usr/lib/sendmail','-f', sender, recipient), stdin = subprocess.PIPE)
        s.stdin.write(content)
        s.stdin.close()
        
def front_page(title, url):

    
    # data = io.BytesIO()
    # pdf = reportlab.pdfgen.canvas.Canvas(data)
    # pdf.drawString(x=33, y=550, text=title)
    # pdf.drawString(x=148, y=590, text=url)
    # pdf.save()
    # data.seek(0)

    data = io.BytesIO()
    tstyle = reportlab.lib.styles.ParagraphStyle('Title')
    bstyle = reportlab.lib.styles.ParagraphStyle('body')
    l = []
    l.append( reportlab.platypus.Paragraph('<a href="%s">%s</a>' % (url, doc.title()), tstyle))
    l.append( reportlab.platypus.Paragraph('<a href="%s">%s</a>' % (url, url), bstyle))

    d = reportlab.platypus.SimpleDocTemplate(data)
    d.multiBuild(l)
    
    data.seek(0)
    return data

def url_to_pdf_wep(url):
    w = weasyprint.HTML(url = url)
    wepoutput = io.BytesIO()

    w.write_pdf( target = wepoutput )

    wepoutput.seek(0)
    
    return wepoutput

def url_to_pdf_pk(url):
    p = pdfkit.from_url(url, output_path = 0)

    i = io.BytesIO()
    i.write( p)
    i.seek(0)
        
    return i
    
last = '1970-01-01'

db = dbm.open('%s/.simple-kindle-sender-database' % os.environ['HOME'],'c')
cookies = get_w3m_cookies()

if 'last' in db:
    # Saved timestamp.
    last = db['last']
    

p = pocket.Pocket(
    consumer_key=consumerkey,
	access_token=token
    )

current = p.get(since=last)
l = current[0]['list']

i = 0

for q in l:
    i = i+1
    if (not q in db):
        
        obj = l[q]

        if 'resolved_url' not in obj:
            continue

        url = obj['resolved_url']
        title = obj['title']
        
        try:
            
            response = requests.get(url)


            content = response.text

            pf = None
            print(url)
            try:
                pf = url_to_pdf_wep(url)
            except:
                print('falling back to pdfkit')
                pf = url_to_pdf_pk(url)



            print("Converted to pdf")
            p = pdfrw.PdfReader(pf)
            front = pdfrw.PdfReader(front_page(title,
                                                   url))
            

            writer = pdfrw.PdfWriter()
            writer.addpages(front.pages)
            writer.addpages(p.pages)
            

            realoutput = io.BytesIO()
            writer.write(realoutput)
            realoutput.seek(0)
            print("Only need to send")

            m = file_to_mail(realoutput.read(),
                                 sender,
                                 recipient,
                                 '%s.pdf' % title )
            send_mail(m.as_bytes(),  sender, recipient)

            #m = file_to_mail(o
            
            db[q] = 'Seen'
        except Exception as e:
            print(e)


db.close()

raise SystemExit
        
