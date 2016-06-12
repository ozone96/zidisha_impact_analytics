from bs4 import BeautifulSoup as soup
from urllib import urlopen
from random import randint
import csv
from havenondemand.hodclient import *
from numpy import mean
from math import ceil
import h2o
from os.path import abspath
import re
client = HODClient("00f24d20-81fa-43c4-a670-9b63992cc0e1", version = 'v1')
h2o.init()

n = 5
client = HODClient("00f24d20-81fa-43c4-a670-9b63992cc0e1", version = 'v1')
outfile = open("testfile.csv", "wr")
writer = csv.writer(outfile)
writer.writerow(['amount','cost','ratio','duration','city','country'])
url = "https://www.zidisha.org/lend"
html = urlopen(url)
bsobj = soup(html.read())
mydivs = bsobj.findAll("div", {"class" : "profile-image-container"})
links = [prof.a.get('href') for prof in mydivs]
print(links)
for i in range(n):
	borrowurl = links[i]
	html = urlopen(borrowurl)
	bsobj = soup(html.read())
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
	strongs = bsobj('strong', text = re.compile(r'months'))
	duration = strongs[0].get_text()
	duration = ''.join(s for s in duration if ord(s)>31 and ord(s)<126)
	duration = duration.replace(' ','')
	duration = duration.replace("months",'')
	duration = int(duration)
	writer.writerow([amount, cost, ratio, duration, city, country])
outfile.close()

resultsfile = open("results.csv","wr")
resultwriter = csv.writer(resultsfile)
resultwriter.writerow(["url", "score"])
from h2o.estimators.glm import H2OGeneralizedLinearEstimator as glme
trainingdf = h2o.import_file(path = abspath('./trainingset.csv'))
trainingdf["city"] = trainingdf["city"].asfactor()
trainingdf["country"] = trainingdf["city"].asfactor()
glm_classifier = glme(family="gaussian")
glm_classifier.train(x = ['amount','cost','ratio','duration','city','country'],y = 'score', training_frame = trainingdf)
testdf = h2o.import_file(path = abspath('./testfile.csv'))
print(testdf)
result = h2o.as_list(glm_classifier.predict(testdf), use_pandas = False)
result.pop(0)
result = [float(r[0]) for r in result]
print(result)
for i in range(n):
	resultwriter.writerow([links[i],result[i]])
