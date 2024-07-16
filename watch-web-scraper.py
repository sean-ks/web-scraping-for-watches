import requests
from bs4 import BeautifulSoup
import csv
import sys
import re
import pandas as pd
import re
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import set_with_dataframe
from selenium import webdriver

website = input("eBay (type e) or watchcharts (type w):")
search_term = input("Enter the search term/reference number:\n")


def wholeWordCheck(word, item):
    if re.compile(r'\b({0})\b'.format(word), re.IGNORECASE).search(item) is not None:
        return True
    return False


#checks if the item matches the key searches
def exactWordCheck(search, item, index):
    if len(search.split(' ')) == index:
        return True
    return wholeWordCheck(search.split(' ')[index], item) and exactWordCheck(search, item, index + 1)


# returns the "soup" of the
def get_soup(search_term, website):
    search = "\"" + search_term.replace(' ', '"+"') + "\""
    print("searched for: " + search)
    while (True):
        if (website == "e"):
            url = f'https://www.ebay.com/sch/i.html?_nkw={search}&_sacat=0&LH_TitleDesc=1&_odkw={search}&_osacat=0&_sop=12'
            break
        if (website == "w"):
            url = f"https://watchcharts.com/watches?keyword={search}"
            break
        if (
                website == "a"):  #the method runs again in parseWatch, website can only be == a if it goes through parseWatch
            url = search_term
            break
        website = input("eBay (type e) or watchcharts (type w):")

    #uses firefox web bot to access the website and scrapes the data from it
    driver = webdriver.Firefox()
    driver.get(url)
    r = driver.page_source
    soup = BeautifulSoup(r, "lxml")
    driver.quit()
    name = find("h4", {"class": "m-0 font-weight-bolder"}).text

    if name is None:
        print("can't find " + search_term + "... Exiting program")
        exit(1)

    confirm = input("Is " + name + " what you are looking for? (y/n)")
    if confirm == "n":
        print("exiting program...")
        exit(1)

    return soup


# parses the data for ebay
def parseEbay(soup):
    listings = soup.find_all("div", {'class': "s-item__info clearfix"})
    images = soup.find_all("div", {'class': "s-item__wrapper clearfix"})
    result_list = []
    for listing, image_container in zip(listings, images):
        title = listing.find("div", {'class': "s-item__title"}).text
        if exactWordCheck(search_term, title, 0) is False:
            continue
        price = listing.find("span", {'class': "s-item__price"}).text
        product_url = listing.find("a", {'class': "s-item__link"}).attrs["href"]

        product_status_element = listing.find("div", {'class': "s-item__subtitle"})
        product_status = (
            product_status_element.text
            if product_status_element is not None
            else "No status available"
        )
        if title and price:
            title_text = title.strip()
            price_text = price.strip()
            status = product_status.strip()

            image = image_container.find("div", {'class': "s-item__image"})
            img = image.find("img").attrs["src"]
            result_dict = {
                "title": title_text,
                "price in USD": float(price_text.replace('$', '').replace(',', '')),
                "image_url": img,
                "status": status,
                "link": product_url,
            }
            result_list.append(result_dict)
    return result_list


# parses the data for watchcharts
def parseWatch(soup):
    watchURL = soup.find("a", {'class': "flex-fill text-decoration-none"}).attrs['href'].split("-")
    watchID = watchURL[0][13:]
    url = f"https://marketplace.watchcharts.com/listings/limit/120?redirect=%2Flistings%2Fwatch_model%2F{watchID}%3Fold=1"
    watchSoup = get_soup(url, "a")

    product_list = []
    listings = watchSoup.find_all("div",
                                  {'class': "align-self-stretch position-relative listing-card-fixed-width px-2 pb-3"})

    for listing in listings:
        title = listing.find("p", {'class': ["card-title card-title-watch bg-white m-0 ddd-truncated",
                                             "card-title card-title-watch bg-white m-0"]}).text
        price = listing.find("h4", {'class': "m-0"}).text
        if price[1] != "$":
            continue
        product_url = listing.find_all("a", {'class': "card-link"})[1].attrs["href"]
        image_url = listing.find("img", {'class': "card-img-top lazy lazy-image loaded"}).attrs["src"]
        seller = listing.find("a", {'class': "stretched-link card-link text-black"}).attrs["href"]
        date_listed = listing.find("time").attrs["datetime"]
        source = listing.find("img", {'class': "card-icon"}).attrs["aria-label"]
        sold = False
        if title.strip()[0:4] == "SOLD":
            sold = True

        result_dict = {
            "title": title.strip().replace("SOLD", "").replace("NEW", ""),
            'price in USD': float(price.strip().replace('$', '').replace(',', '')),
            "image_url": image_url,
            "link": "#".join([url, product_url]),
            "seller": seller,
            "date_listed": date_listed,
            "sold": sold,
            "source": source,
        }
        product_list.append(result_dict)

    # aggregate from ebay
    url = f"https://marketplace.watchcharts.com/listings/limit/120?redirect=%2Flistings%2Fwatch_model%2F{watchID}%3Fold=1%26source%3Debay"
    watchSoup = get_soup(url, "a")
    print(watchSoup.prettify())
    listings = watchSoup.find_all("div", {'class': 'px-2 mb-3 listing-card-fixed-width'})

    for listing in listings:
        title = listing.find("p", {'class': ['text-break card-title card-title-watch bg-white ddd-truncated',
                                             'text-break card-title card-title-watch bg-white']}).text
        price = listing.find("h4", {'class': "m-0"}).text
        product_url = listing.find("a", {"class": "card-link"}).attrs["href"]
        image_url = listing.find("img", {'class': "card-img-top lazy lazy-image loaded"}).attrs["src"]
        seller = listing.find("p", {'class': 'mb-0 font-weight-bold text-nowrap overflow-hidden'}).text
        sold = False
        if title.strip()[0:4] == "SOLD":
            sold = True

        result_dict = {
            "title": title.strip().replace("SOLD", "").replace("NEW", ""),
            'price in USD': float(price.strip().replace('$', '').replace(',', '')),
            "image_url": image_url,
            "link": "#".join([url, product_url]),
            "seller": seller,
            "date_listed": "N/A",
            "sold": sold,
            "source": "eBay",
        }
        product_list.append(result_dict)

    return product_list


#the data scraped from the websites gets put into a csv file and displayed in histograms
def output(result_list):
    df = pd.DataFrame(result_list)
    stdev = df['price in USD'].std()
    median = df['price in USD'].median()
    mean = df['price in USD'].mean()
    if stdev > median or stdev > mean:
        df1 = df[df['price in USD'] <= stdev]
        df1['price in USD'].plot.hist(bins=10)
        plt.title('(Lower than stdev) Price in USD for ' + search_term)
        plt.xlabel('Price in USD, mean = ' + str(int(df1['price in USD'].mean())) + ", median = " + str(
            df1['price in USD'].median()) + ", stdev = " + str(df1['price in USD'].std()))
        plt.show()

        df2 = df[df['price in USD'] >= stdev]
        df2['price in USD'].plot.hist(bins=10)
        plt.title('(Higher than stdev) Price in USD for ' + search_term)
        plt.xlabel('Price in USD, mean = ' + str(int(df2['price in USD'].mean())) + ", median = " + str(
            df2['price in USD'].median()) + ", stdev = " + str(df2['price in USD'].std()))
        plt.show()
    else:
        df['price in USD'].plot.hist(bins=10)
        plt.title('Price in USD for ' + search_term)
        plt.xlabel('Price in USD, mean = ' + str(int(df['price in USD'].mean())) + ", median = " + str(
            df['price in USD'].median()) + ", stdev = " + str(df['price in USD'].std()))
        plt.show()

    df.to_csv("watches.csv", index=False)
    print("saved to csv")
    return


while (True):
    if website == "e":
        soup = get_soup(search_term, website)
        result_list = parseEbay(soup)
        output(result_list)
        break
    elif website == "w" or website == "a":
        soup = get_soup(search_term, website)
        result_list = parseWatch(soup)
        output(result_list)
        break
    else:
        website = input("Enter the website you want to scrape (e for ebay, w for watchcharts): ")
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/spreadsheets',
         "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]

#censored for privacy
folderId = "#################"
credentials = ServiceAccountCredentials.from_json_keyfile_name('##################', scope)
client = gspread.authorize(credentials)

file_name = input("Enter the file name: ")
workbook = client.create(file_name, folder_id=folderId)
spreadsheet = client.open(file_name)

with open('watches.csv', 'r') as file_obj:
    content = file_obj.read()
    client.import_csv(spreadsheet.id, data=content)

print("created google sheets")
