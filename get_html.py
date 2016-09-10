import urllib2
from HTMLParser import HTMLParser
from bs4 import BeautifulSoup
import sqlite3

conn = sqlite3.connect('data.sqlite')
c = conn.cursor()
c.execute('delete from works')
conn.commit()

target = open('data.csv', 'w')

for i in range(1,54):
	response = urllib2.urlopen('http://www.businessoulu.com/en/company-services/online-services/company-database/search.html?category=&q=oulu&z=asc&s=&p5286='+ str(i))
	html = response.read()
	soup = BeautifulSoup(html, 'lxml')
	items = soup.body.find_all('div', attrs={'class':'firm-search__item clearfix'})
	for item in items:
		name = item.find('div', attrs={'class':'firm-search__item__content'}).h4.a.text
		link = item.find('div', attrs={'class':'firm-search__item__content'}).h4.a['href']
		response_item = urllib2.urlopen(link)
		html_item = response_item.read()
		soup_item = BeautifulSoup(html_item, 'lxml')
		try:
			item_info = soup_item.body.find('div', attrs={'class':'slot-target__info'}).find_all('p')
			address = str(item_info[0]).split('<br/>')[0].replace('p', '')
			mail_address = str(item_info[0]).split('<br/>')[1].replace('\r', '').replace('\n', '')
			size = item_info[3].text.replace('\r', '').replace('\n', '')
		
		#print(unicode(name, 'utf8') + ',' + unicode(address, 'utf8') +  ',' + unicode(mail_address, 'utf8') +  ',' + unicode(size, 'utf8'))
		
			target.write(name + ',' + address + ','  + mail_address + ','  + size + ',' + link)
		except:
			target.write(',,,,' + link)
		target.write('\n')
		
		target.flush()

		'''t = ('RHAT',)
		c.execute('insert into works (name, address, mail_address, size) values (?, ?, ?, ?)', (str(name), str(address), str(mail_address), str(size)))
		conn.commit()'''