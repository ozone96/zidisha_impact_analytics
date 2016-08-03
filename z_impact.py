from bs4 import BeautifulSoup as soup
from urllib import urlopen
from random import randint, choice
import csv
from havenondemand.hodclient import *
from numpy import mean
from math import ceil
import re
import h2o
from os.path import abspath, basename, isfile
from os import curdir, rename
import os
from scipy.stats import pearsonr
from math import sqrt
import json

					#please don't steal my API key...
client = HODClient("00f24d20-81fa-43c4-a670-9b63992cc0e1", version = 'v1') #open a Haven OnDemand client

def profile(url): #get general information about the loan and borrower
	html = urlopen(url)
	bsobj = soup(html.read(), 'html.parser')
	strongs = bsobj('strong', text = re.compile(r'\$')) #find bolded text containing $
	amount = float(strongs[0].get_text().replace("$","").replace(',','')) #loan amount is the first
	cost = float(strongs[1].get_text().replace("$","").replace(',','')) #loan cost is the second
	ratio = cost/amount #relative cost may matter as well as absolute cost
	strongs = bsobj('strong')
	location = strongs[1].get_text() #the second <strong> is always the location
	location = ''.join(s for s in location if ord(s)>31 and ord(s)<126) #get rid of special and non-ascii characters
	location = location.replace(' ','') #remove extraneous spaces
	location = location.split(',')
	city = location[0] 
	country = location[1]
	strongs = bsobj('strong', text = re.compile(r'month')) #loan period should be the only bolded text with "month" in it
	duration = strongs[0].get_text()
	duration = ''.join(s for s in duration if ord(s)>31 and ord(s)<126) #remove special characters
	duration = duration.replace(' ','') #remove spaces
	duration = duration.replace("months",'') #get just the number of months by itself
	duration = duration.replace("month",'')
	duration = int(duration)
	strongs = bsobj('strong', text = re.compile(r'\%\n'))
	if len(strongs) == 0: #if the borrower is new, we give them the benefit of the doubt
		record = 1.
		history = 0
	else:
		past = strongs[0].get_text()
		record = re.findall(re.compile(r'..\%|...\%'), past)[0]
		record = float(record.replace('%',''))/100. #what proportion of past repayments were on time
		history = re.findall(re.compile(r'\(.+\)'), past)[0]
		history = int(history.replace('(','').replace(')','')) #number of past repayments
	return [url, amount, cost, ratio, duration, city, country, record, history]

def profileNLData(surl, trainnum, testnum):
	n = trainnum + testnum
	url = surl
	for x in range(n):
		dataDict = {}
		dataDict["url"] = url
		html = urlopen(url)
		bsobj = soup(html.read(), 'html.parser')
		bolds = bsobj('strong')
		name = bolds[0].get_text() # Name is the first bolded item 
		print name
		dataDict["name"] = name
		data = bsobj.find_all("div", { "class" : "loan-section" })
		for item in data:
			data2 = item.find_all("span")
			if data2[0].get_text() == "Story": # If we are on the story part:
				data3 = item.find_all("div", {"class" : "loan-section-content"})
				nldata = data3[0].get_text()

		dataDict["nldata"] = nldata
		print dataDict
		if not os.path.exists(".profiletext/"):
		    os.makedirs(".profiletext/")

		f = open(".profiletext/" + name.replace(" ", "_") + ".json", "w")
		f.write(json.dumps(dataDict))
		try:
			url = nextborrower(url) #temporary kludge: if we run into a dead end, just go back to start
		except AssertionError:
			url = start


#TO DO: for a given loan, take only the comments that fall within the period of that particular loan (currently, comments for the same borrower are all lumped together)
def getscore(url): #does sentiment analysis on the comment thread for a given loan
	html = urlopen(url + '/discussion') 
	bsobj = soup(html.read(), 'html.parser')
	mydivs = bsobj.findAll("div", {"class" : "media-body"})
	comments = [div.p.get_text() for div in mydivs]
	if len(comments) > 0:
		comment = " ".join(comments)
		comment = comment.replace("   ", "") #there is often a lot of extra whitespace. get rid of that. 
		chunks = re.findall(re.compile(r'.{1,1000}', re.DOTALL),comment) #chunks of text larger than 1-2k characters often don't seem to get processed properly. this is really kludgy, though. 
		chunks = [''.join(s for s in chunk if ord(s)>31 and ord(s)<126) for chunk in chunks] #get rid of special and non-ascii characters
		scores = []
		for chunk in chunks:
			analysis = client.get_request({"text" : chunk}, HODApps.ANALYZE_SENTIMENT, async=False) #sentiment analysis of each chunk
			scores.append(analysis["aggregate"]["score"])
		score = mean(scores)
	else:
		score = 0.
	return score

def nextborrower(url): #there's no centralized page that lists all past loans on Zidisha, so we need to do some crawling to find the next loan page
	html = urlopen(url)
	bsobj = soup(html.read(), 'html.parser')
	mydivs = bsobj.findAll("div", {"class" : "lender-thumbnail"}) #get all the lenders who contributed
	otherborrowers = []
	tries = 0
	#keep trying until we find a lender with at least one other borrower listed on their page. there should be a more systematic way to do this to avoid repeats and reduce runtime. 
	while (len(otherborrowers) == 0) and (tries < 30):
		choice = mydivs[randint(0,len(mydivs)-1)]
		lendurl = choice.a.get('href')
		html = urlopen(lendurl)
		bsobj = soup(html.read(), 'html.parser')
		mydivs2 = bsobj.findAll("div", {"class" : "lender-thumbnail"}) #find all the borrowers that lender has given to
		if len(mydivs2) > 1:
			otherborrowers = mydivs2
			choice = mydivs2[randint(0,len(mydivs2)-1)]
			borrowurl = choice.a.get('href')
		tries += 1
	assert tries < 30
	return borrowurl

def buildmodel(): #trains, saves, and validates a model
	trainmodel()
	testdf = h2o.import_file(path = abspath('./testset.csv'))
	result = evalmodel(testdf) #attempt to predict scores
	target = h2o.as_list(testdf["score"], use_pandas = False) #get the actual scores to compare prediction with actual result
	target.pop(0)
	target = [float(t[0]) for t in target]
	cor = pearsonr(result, target)
	mse = mean([(result[i] - target[i])**2. for i in range(len(target))])
	#print validation info
	print('Correlation: r = ' + str(cor[0]) + ' p = ' + str(cor[1]))
	print('Mean squared error: ' + str(mse))

#TO DO: restrict training and testing data to loans for which the final repayment date has passed
#TO DO: allow this function to add data to an existing data set instead of writing a new file each time
def getdata(start, n, m, addn, addm):
	url = start
	if addn and isfile("./trainingset.csv"):
		readfile = open('trainingset.csv', 'r')
		rd = csv.reader(readfile, delimiter = ',')
		urls = [row[0] for row in rd]
		urls.pop(0)
		url = nextborrower(choice(urls))
		outfile = open('trainingset.csv', 'a')
		writer = csv.writer(outfile)
	else:
		outfile = open('trainingset.csv','wr')
		writer = csv.writer(outfile)
		writer.writerow(['url','amount','cost','ratio','duration','city','country','record','history','score'])
	if addm and isfile("./testset.csv"):
		outfile2 = open("testset.csv", 'a')
		writer2 = csv.writer(outfile2)
	else:
		outfile2 = open('testset.csv','wr')
		writer2 = csv.writer(outfile2)
		writer2.writerow(['url','amount','cost','ratio','duration','city','country','record','history','score'])

	
	for i in range(n + m):
		print(url)
		score = getscore(url)
		info = profile(url)
		if i < n:
			writer.writerow(info + [score])
		else:
			writer2.writerow(info + [score])
		try:
			url = nextborrower(url) #temporary kludge: if we run into a dead end, just go back to start
		except AssertionError:
			url = start
	outfile.close()
	outfile2.close()

def trainmodel():
	h2o.init()
	from h2o.estimators.glm import H2OGeneralizedLinearEstimator as glme
	trainingdf = h2o.import_file(path = abspath('./trainingset.csv'))
	trainingdf["city"] = trainingdf["city"].asfactor()
	trainingdf["country"] = trainingdf["city"].asfactor()
	glm_classifier = glme(family = "gaussian")
	glm_classifier.train(x = ['amount','cost','ratio','duration','city','country','record','history'],y = 'score', training_frame = trainingdf)
	savedir = h2o.save_model(glm_classifier, path = curdir, force = True)
	rename(basename(savedir),"model")

def evalmodel(df):
	glm_classifier = h2o.load_model('./model')
	result = h2o.as_list(glm_classifier.predict(df), use_pandas = False)
	result.pop(0) #get rid of the column header
	result = [float(r[0]) for r in result] #the results are each returned as 1-element lists. fix that. 
	return result

def frontpage(n): #generates scores for the first n loans listed on Zidisha's main page and writes a csv file of them
	url = "https://www.zidisha.org/lend"
	html = urlopen(url)
	bsobj = soup(html.read(), 'html.parser')
	mydivs = bsobj.findAll("div", {"class" : "profile-image-container"})
	fpfile = open('frontpage.csv','wr')
	fpwriter = csv.writer(fpfile)
	fpwriter.writerow(['amount','cost','ratio','duration','city','country','record','history'])
	links = [prof.a.get('href') for prof in mydivs]
	titles = []
	for i in range(n):
		fpwriter.writerow(profile(links[i]))
		html = urlopen(links[i])
		bsobj = soup(html.read(), 'html.parser')
		hits = bsobj.findAll('p',{'class' : 'alpha'})
		titles.append(hits[0].get_text().replace('  ','').replace('\n',''))
	fpfile.close()
	h2o.init()
	from h2o.estimators.glm import H2OGeneralizedLinearEstimator as glme
	fpdf = h2o.import_file(path = abspath('./frontpage.csv'))
	result = evalmodel(fpdf)
	resultfile = open('results.csv','wr')
	resultwriter = csv.writer(resultfile)
	resultwriter.writerow(['project','url','score'])
	for i in range(n):
		resultwriter.writerow([titles[i],links[i],result[i]])

# Gets data for GLM
def executable1():
	starturl = "https://www.zidisha.org/loan/uang-untuk-melanjutkan-pendidikan-ke-universitas"
	n = 2
	getdata(starturl, n, n, True, True)
	#buildmodel()
	#frontpage(10)

# Gets data for nl data for RNN. Stores it to .profiletext/{name}.json
def executable2():
	starturl = "https://www.zidisha.org/loan/uang-untuk-melanjutkan-pendidikan-ke-universitas"
	n = 50
	profileNLData(starturl, n, n)
	pass


if __name__ == "__main__":
	executable1()
