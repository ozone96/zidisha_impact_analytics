from bs4 import BeautifulSoup as soup
from urllib import urlopen
from random import randint
import csv
from havenondemand.hodclient import *
from numpy import mean
from math import ceil
import re

client = HODClient("00f24d20-81fa-43c4-a670-9b63992cc0e1", version = 'v1')

outfile = open('sentiment.csv','wr')
outfile2 = open('trainingset.csv', 'wr')
writer = csv.writer(outfile)
writer.writerow(['url','score','qual'])
writer2 = csv.writer(outfile2)
writer2.writerow(['amount','cost','ratio','duration','city','country','score'])
#writer2.writerow(['DOUBLE','DOUBLE','DOUBLE','INTEGER','RICH_TEXT','RICH_TEXT','DOUBLE'])
n = 100

borrowurl = "https://www.zidisha.org/loan/uang-untuk-melanjutkan-pendidikan-ke-universitas"
for i in range(n):
	print(borrowurl)
	#get sentiment analysis of the comment thread on the project
	html = urlopen(borrowurl + "/discussion")
	bsobj = soup(html.read(), 'lxml')
	mydivs = bsobj.findAll("div", {"class" : "media-body"})
	comments = [div.p.get_text() for div in mydivs]
	if len(comments) > 0:
		comment = " ".join(comments)
		if len(comment) > 3000:
			comment = comment[:3000]
		analysis = client.get_request({"text" : comment}, HODApps.ANALYZE_SENTIMENT, async=False)
		print(analysis)
		avg = analysis["aggregate"]["score"]
	else:
		avg = 0.
	qual = int(ceil(avg))
	writer.writerow([borrowurl, avg, qual])
	html = urlopen(borrowurl)
	bsobj = soup(html.read(), 'lxml')
	#retrieve the other pieces of information about the borrower that we will be using to make predictions
	strongs = bsobj('strong', text = re.compile(r'\$'))
	amount = float(strongs[0].get_text().replace("$","").replace(',',''))
	cost = float(strongs[1].get_text().replace("$","").replace(',',''))
	ratio = cost/amount
	strongs = bsobj('strong')
	location = strongs[1].get_text() #the second <strong> is always the location
	location = ''.join(s for s in location if ord(s)>31 and ord(s)<126) #get rid of special and non-ascii characters
	location = location.replace(' ','') #remove extraneous spaces
	location = location.split(',')
	city = location[0]
	country = location[1]
	strongs = bsobj('strong', text = re.compile(r'month'))
	duration = strongs[0].get_text()
	duration = ''.join(s for s in duration if ord(s)>31 and ord(s)<126)
	duration = duration.replace(' ','')
	duration = duration.replace("months",'')
	duration = int(duration)
	writer2.writerow([amount, cost, ratio, duration, city, country, avg])
	#retrieve lenders to find the next borrower
	mydivs = bsobj.findAll("div", {"class" : "lender-thumbnail"})
	otherborrowers = []
	tries = 0
	#keep trying until we find a lender with at least one borrower listed on their page
	while (len(otherborrowers) == 0) and (tries < 30):
		choice = mydivs[randint(0,len(mydivs)-1)]
		lendurl = choice.a.get('href')
		html = urlopen(lendurl)
		bsobj = soup(html.read(), 'lxml')
		mydivs2 = bsobj.findAll("div", {"class" : "lender-thumbnail"})
		if len(mydivs2) > 0:
			otherborrowers = mydivs2
			choice = mydivs2[randint(0,len(mydivs2)-1)]
			borrowurl = choice.a.get('href')
		tries += 1
	assert tries < 30