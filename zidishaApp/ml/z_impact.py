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
from datetime import datetime

					#please don't steal my API key...
client = HODClient("00f24d20-81fa-43c4-a670-9b63992cc0e1", version = 'v1') #open a Haven OnDemand client

def profile(url): #get general information about the loan and borrower
	html = urlopen(url)
	bsobj = soup(html.read(), 'html.parser')
	strongs = bsobj('strong', text = re.compile(r'\$')) #find bolded text containing $
	amount = float(strongs[0].get_text().replace("$","").replace(',','')) #loan amount is the first
	col = bsobj('div', {'class' : 'col-sm-6'})[2]
	if "Date Disbursed" in col.get_text(): 
		cost = float(strongs[1].get_text().replace("$","").replace(',','')) #loan cost is the second for disbursed loans
	else:
		cost = float(strongs[2].get_text().replace("$","").replace(',','')) #loan cost is the third for loans currently funding
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
		history = 0
		ontime = 0
		notontime = 0
	else:
		past = strongs[0].get_text()
		record = re.findall(re.compile(r'.{1,3}\%'), past)[0]
		record = float(record.replace('%',''))/100. #what proportion of past repayments were on time
		history = re.findall(re.compile(r'\(.+\)'), past)[0]
		history = int(history.replace('(','').replace(')','')) #number of past repayments
		ontime = int(record*history)
		notontime = history - ontime
	strongs = bsobj('strong', text = re.compile(r'% Positive'))
	if len(strongs) > 0:
		feedback = strongs[0].get_text()
		prop = re.findall(re.compile(r'.{1,3}\%'), feedback)[0]
		prop = float(prop.replace('%', ''))/100.
		nvotes = re.findall(re.compile(r'\(.+\)'), feedback)[0]
		nvotes = int(nvotes.replace('(','').replace(')',''))
		posvote = int(prop*nvotes)
		negvote = nvotes - posvote
	else:
		posvote = 0
		negvote = 0
	div = bsobj('div',{'id' : 'show-calculation'})[0]
	ps = div('p')
	fees = 0.
	for p in ps:
		if ('lifetime membership' in p.get_text()) or ('opted to pay' in p.get_text()):
			fee = float(p.strong.get_text().replace('$',''))
			fees += fee
	hits = bsobj.findAll('p',{'class' : 'alpha'})
	title = hits[0].get_text().replace('  ','').replace('\n','')
	title = ''.join(s for s in title if ord(s) > 31 and ord(s) < 126)
	data = bsobj.find_all("div", { "class" : "loan-section" })
	for item in data:
		data2 = item.find_all("span")
		if data2[0].get_text() == "Story": # If we are on the story part:
			data3 = item.find_all("div", {"class" : "loan-section-content"})
			description = data3[0].get_text()
			description = ''.join(s for s in description if ord(s)>31 and ord(s)<126)
			description = description.split("Show original")[0].replace('About Me','').replace('\n',' ').replace('My Business','').replace('Loan Proposal','').replace('   ','')
	feeratio = fees/amount
	return [url, amount, cost, ratio, duration, city, country, ontime, notontime, history, posvote, negvote, fees, feeratio, title, description]

'''
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
'''

#TO DO: for a given loan, take only the comments that fall within the period of that particular loan (currently, comments for the same borrower are all lumped together)
def getscore(url): #does sentiment analysis on the comment thread for a given loan
	html = urlopen(url + '/discussion') 
	bsobj = soup(html.read(), 'html.parser')
	html2 = urlopen(url)
	bsobj2 = soup(html2.read(), 'html.parser')
	col = bsobj2('div', {'class' : 'col-sm-6'})[2]
	if "Date Disbursed" in col.get_text(): 
		cutoff = datetime.strptime(col('strong')[1].get_text(), '%b %d, %Y').date()
		if len(col('strong', text = re.compile(r'On Time'))) > 0:
			ontime = 1
		else:
			ontime = 0
	else:
		cutoff = datetime.now().date()
		ontime = 1
	mydivs = bsobj.findAll("div", {"class" : "media-body"})
	comments = [div.p.get_text() for div in mydivs]
	spans = bsobj('span', {'class' : 'comment-actions'})
	dates = [datetime.strptime(span.get_text(), '%b %d, %Y').date() for span in spans]
	beforecomments = [comments[i] for i in range(len(comments)) if dates[i] < cutoff]
	aftercomments = [comments[i] for i in range(len(comments)) if dates[i] >= cutoff]
	if len(beforecomments) > 0:
		comment = " ".join(beforecomments)
		comment = comment.replace("   ", "").replace("&","and").replace("#","") #there is often a lot of extra whitespace. get rid of that. Also, ampersands and pound signs seem to cause a problem, so toss 'em.
		chunks = re.findall(re.compile(r'.{1,1000}', re.DOTALL),comment) #chunks of text larger than 1-2k characters often don't seem to get processed properly. this is really kludgy, though. 
		chunks = [''.join(s for s in chunk if ord(s)>31 and ord(s)<126) for chunk in chunks] #get rid of special and non-ascii characters
		scores = []
		for chunk in chunks:
			analysis = client.get_request({"text" : chunk}, HODApps.ANALYZE_SENTIMENT, async=False) #sentiment analysis of each chunk
			scores.append(analysis["aggregate"]["score"])
		beforescore = mean(scores)
	else:
		beforescore = 0.
	if len(aftercomments) > 0:
		comment = " ".join(aftercomments)
		comment = comment.replace("   ", "") #there is often a lot of extra whitespace. get rid of that. 
		chunks = re.findall(re.compile(r'.{1,1000}', re.DOTALL),comment) #chunks of text larger than 1-2k characters often don't seem to get processed properly. this is really kludgy, though. 
		chunks = [''.join(s for s in chunk if ord(s)>31 and ord(s)<126) for chunk in chunks] #get rid of special and non-ascii characters
		scores = []
		for chunk in chunks:
			analysis = client.get_request({"text" : chunk}, HODApps.ANALYZE_SENTIMENT, async=False) #sentiment analysis of each chunk
			scores.append(analysis["aggregate"]["score"])
		afterscore = mean(scores)
	else:
		afterscore = 0.
	return beforescore, afterscore, ontime

def nextborrower(url, urls): #there's no centralized page that lists all past loans on Zidisha, so we need to do some crawling to find the next loan page
	maxtries = 30
	borrowurl = ""
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
	if borrowurl in urls:
		return nextborrower(url, urls) #if this borrower has already been used, recursively go back to the beginning. A bit kludgy. 
	html = urlopen(borrowurl)
	bsobj = soup(html.read(), 'html.parser')
	col = bsobj('div', {'class' : 'col-sm-6'})[2].get_text()
	if "Date Disbursed" not in col: #if the loan hasn't been disbursed yet, don't use it for training or validation
		return nextborrower(url, urls)
	assert tries < maxtries
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
	urls = []
	if addn and isfile("./trainingset.csv"):
		readfile = open('trainingset.csv', 'r')
		rd = csv.reader(readfile, delimiter = ',')
		urls = [row[0] for row in rd]
		urls.pop(0)
		readfile.close()
		outfile = open('trainingset.csv', 'a')
		writer = csv.writer(outfile)
	else:
		outfile = open('trainingset.csv','wr')
		writer = csv.writer(outfile)
		writer.writerow(['url','amount','cost','ratio','duration','city','country','ontime','notontime','history','posvote','negvote','fees','feeratio','title','description','pastscore','score', 'ontime'])
	if addm and isfile("./testset.csv"):
		readfile = open('testset.csv', 'r')
		rd = csv.reader(readfile, delimiter = ',')
		urls2 = [row[0] for row in rd]
		urls2.pop(0)
		ursl = urls + urls2
		outfile2 = open("testset.csv", 'a')
		writer2 = csv.writer(outfile2)
	else:
		outfile2 = open('testset.csv','wr')
		writer2 = csv.writer(outfile2)
		writer2.writerow(['url','amount','cost','ratio','duration','city','country','ontime','notontime','history','posvote','negvote','fees','feeratio','title', 'description', 'pastscore','score', 'ontime'])
	urlset = set(urls)
	if len(urls) > 0:
		url = nextborrower(choice(urls), urlset)
	
	for i in range(n + m):
		print(url)
		pastscore, score, ontime = getscore(url)
		info = profile(url)
		if i < n:
			writer.writerow(info + [pastscore, score, ontime])
		else:
			writer2.writerow(info + [pastscore, score, ontime])
		try:
			url = nextborrower(url, urlset) #temporary kludge: if we run into a dead end, just pick a random url that we've visited before and go from there
			urlset.add(url)
		except AssertionError:
			url = choice(list(urlset))
	outfile.close()
	outfile2.close()

def trainmodel():
	h2o.init()
	from h2o.estimators.glm import H2OGeneralizedLinearEstimator as glme
	trainingdf = h2o.import_file(path = abspath('./trainingset.csv'))
	trainingdf["city"] = trainingdf["city"].asfactor()
	trainingdf["country"] = trainingdf["city"].asfactor()
	glm_classifier = glme(family = "gaussian")
	glm_classifier.train(x = ['amount','cost','ratio','duration','city','country','ontime','notontime','history','posvote','negvote','fees','feeratio','pastscore'],y = 'score', training_frame = trainingdf)
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
	fpwriter.writerow(['url','amount','cost','ratio','duration','city','country','ontime','notontime','history','posvote','negvote','fees','feeratio','title', 'description', 'pastscore'])
	links = [prof.a.get('href') for prof in mydivs]
	titles = []
	for i in range(n):
		beforescore, afterscore, ontime = getscore(links[i])
		fpwriter.writerow(profile(links[i]) + [beforescore])
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
	#nextborrower('https://www.zidisha.org/loan/loan-to-expand-my-provision-store', set())
	starturl = "https://www.zidisha.org/loan/uang-untuk-melanjutkan-pendidikan-ke-universitas"
	n = 1000
	getdata(starturl, n, n, True, True)
	#buildmodel()
	#frontpage(5)

# Gets data for nl data for RNN. Stores it to .profiletext/{name}.json
def executable2():
	starturl = "https://www.zidisha.org/loan/uang-untuk-melanjutkan-pendidikan-ke-universitas"
	n = 50
	profileNLData(starturl, n, n)
	pass


if __name__ == "__main__":
	executable1()
