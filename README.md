# Zidisha Impact Analytics
The goal of this project is to provide predictive analytics that will allow microfinance lenders to choose to fund the projects that are most likely to have a positive impact on the borrower. 

##Requirements
Install requirements with "pip install -r requirements.txt"

##Training data
Running z_impact.py scrapes profile information and comment threads from project pages on Zidisha's website and creates a CSV file containing the information obtained along with a sentiment analysis of the comments.
This is a VERY slow process if one wants a large training data set, so if you want to test out the code I recommend using the pre-generated one I've included here. 

##Building a model and scoring
Running front_page.py collects basic profile information from the first several currently funding projects on Zidisha's front page, trains a Gaussian GLM on the training data in trainingset.csv, and assigns predicted impact scores to the new projects based on the model. Output is a csv with the project names, URLs, and scores. 
