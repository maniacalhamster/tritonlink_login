import requests
import getpass
import urllib
import re

# User Data can be imported or grabbed at the very beginning
pid = raw_input('Enter your id: ');
pwd = getpass.getpass('Enter your password: ');

# login session will keep all cookies sent over server, target url will be the
# ucsd student degree audit page
login = requests.Session();
url = 'https://mytritonlink.ucsd.edu';
# For checking response headers for new cookies
# cookie = 'Set-Cookie';

resp = login.get(url, allow_redirects=False);
while not(re.search('jlink', resp.url)):
	resp = login.send(resp.next, allow_redirects=False);
RelayState = resp.url;

# second redirect takes you to the part A of signing in (user credentials)
# page has a POST form to be filled out with user data and sent to itself
sso_es1 = login.send(resp.next);

# print('\nRedirected to: '+sso_es1.url);

# POST form contents are PID, password, and eventId (not sure what this is for)
# POST request sent to self will return a redirect to part B of signing in (DUO) 
login_data = {'urn:mace:ucsd.edu:sso:username':pid, 'urn:mace:ucsd.edu:sso:password':pwd, '_eventId':'proceed'};
sso_es2 = login.post(sso_es1.url, data=login_data);

# pwd = 'Hidden';
# login_data = {'urn:mace:ucsd.edu:sso:username':pid, 'urn:mace:ucsd.edu:sso:password':pwd, '_eventId':'proceed'};
# print('\nPosting login data to: '+sso_es1.url);
# print('Data:');
# for dat in login_data:
	# print('\t'+dat+':\t'+login_data[dat]);

# print('\nRedirected to: '+sso_es2.url);

# POST form contents for the Duo part of signing in is given here but the current
# sig_request is only the <tx> value and not the true sig_request value
data_host = re.search('(?<=data-host=").*com', sso_es2.content).group(0);
data_sig_request = re.search('(?<=data-sig-request=").*==\|.{40}', sso_es2.content).group(0);
data_post_action = re.search('(?<=data-post-action=").*e\d+s\d+', sso_es2.content).group(0);

# print('Extracted Data: \ndata_host:\t'+data_host+'\ndata_sig_request:\t'+data_sig_request+'\ndata_post_action:\t'+data_post_action);

# first, you must complete the duo authentication process, which starts with a
# POST request to the above host name's /frame/web/v1/auth? site with the
# <tx>, <parent>, and <v> query strings (tx is the 'TX portion' of the sig_request from before)
tx = re.search('TX.*(?=:)', data_sig_request).group(0);
parent = urllib.quote_plus(sso_es2.url);
v = '2.3';
auth_url = 'https://'+data_host+'/frame/web/v1/auth?tx='+tx+'&parent='+parent+'&v='+v;

# POST form data for the request to this url will hold the following data:
# most of this data is mimmics what is sent in browser requests, probably some are
# unnecesarry in a CLI (e.g. screen_res, flash, java) but better safe than sorry
auth_data = {'tx':tx, 'parent':sso_es2.url, 'referer':sso_es2.url, 'java_version':'', 'flash_version':'', 
	'screen_resolution_width':'1536', 'screen_resolution_height':'864', 'color_depth':'24',
	'is_cef_browser':'false', 'is_ipad_os':'false'};
# Requires User-Agent and Referer headers to be manually set first
login.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36 Edg/83.0.478.58';
login.headers['Referer'] = auth_url;
# POST request sent will return a redirect to generate a duo authenticate prompt
# and should also set a cookie 
auth_resp = login.post(auth_url, data=auth_data, allow_redirects=False);

# print('\nModifying request headers\nUser-Agent:\t'+login.headers['User-Agent']+'\nReferer:\t'+login.headers['Referer']);
# print('\nPosting duo auth data to: '+auth_url);
# print('Data:');
# for dat in auth_data:
	# print(dat+':\t'+auth_data[dat]);
# print(cookie+': '+auth_resp.headers[cookie]);

prompt = login.send(auth_resp.next);

# print('\nRedirected to: '+prompt.url);

# POST request to the prompt_url with the following form data will send a push
# notification to the listed device (again some data seems extra)
prompt_url = re.search('.*(?=\?sid)',prompt.url).group(0);
sid = re.search('(?<=sid=).*',urllib.unquote(prompt.url)).group(0);
prompt_data = {'sid':sid, 'device':'phone1', 'factor':'Duo Push', 'out_of_date':'',
		'days_out_of_date':'', 'days_to_block':'None'};
prompt_resp = login.post(prompt_url, prompt_data);

# print('\nPosting prompt data to: '+prompt_url);
# print('Data:');
# for dat in prompt_data:
	# print(dat+':\t'+prompt_data[dat]);
# print('Response: '+prompt_resp.content);

# response to the prompt POST will hold a txid needed for the next POST for status
# status POST sent twice, first to check if prompt sent succesfully and the 
# second waits until either user responds on device or timeout occurs
status_url = re.search('.*(?=prompt)', prompt_url).group(0) + 'status';
txid = re.search('(?<=txid": ").*-.{12}', prompt_resp.content).group(0);
status_data = {'sid':sid, 'txid':txid};
status_resp = login.post(status_url, status_data);

# print('\nPosting status data to: '+status_url);
# print('Data:');
# for dat in status_data:
	# print(dat+':\t'+status_data[dat]);
# print('Response: '+status_resp.content);

# upon user approval on their device, the second status POST response will set 
# another cookie and provide a resulting url to send the next POST
status_resp = login.post(status_url, status_data);

# print('\nPosting status data for a second time');
# print('Response: '+status_resp.content);
# print(cookie+':\t'+status_resp.headers[cookie]);

# result_url given in the response of second status post is a lot more work to 
# parse than just adding the txid to the status url (which it is)
result_url = status_url + '/' + txid;
result_data = {'sid':sid};
result_resp = login.post(result_url, result_data);

# print('\nPosting result data to: '+result_url);
# print('Data:');
# for dat in result_data:
	# print(dat+':\t'+result_data[dat]);
# print('Response: '+result_resp.content);

# request header referer changes back to the original duo page url
login.headers['Referer'] = sso_es2.url;

# print('\nModifying request header\n'+'Referer:\t'+login.headers['Referer']);
# print("Combining result's AUTH portion of sig_response with sso_es2's APP portion...");

# The content of this POST to the result url holds the true sig_response needed
# to finally fill the POST form for part B (DUO) in signing in 
# again not sure what _eventId data is for but it pops up both times in browser
# also, the sig_response's AUTH portion comes from the response to the result
# post, hwoever the APP portion comes from the original <tx> back in sse_es2
duo_url = sso_es2.url;
sig_response = re.search('AUTH.*==\|.{40}', result_resp.content).group(0);
sig_response = sig_response+re.search(':APP.*(?=")', sso_es2.content).group(0);
duo_data = {'_eventId':'proceed', 'sig_response':sig_response};
duo_resp = login.post(duo_url, duo_data);

# print('\nPosting duo data to: '+duo_url);
# print('Data:');
# for dat in duo_data:
	# print(dat+':\t'+duo_data[dat]);

# After succesfully completing 2 factor authentication, you are finally given 
# the SAMLResponse (the long successful one!) and can make the FINAL POST to
# the shibboleth url with both RelayState (original site) and SAMLResponse
shibboleth_url = 'https://act.ucsd.edu/Shibboleth.sso/SAML2/POST';
SAMLResponse = re.search('(?<=SAMLResponse" value=").*(?="/>)', duo_resp.content).group(0);
shibboleth_data = {'RelayState':RelayState, 'SAMLResponse':SAMLResponse};
shibboleth_resp = login.post(shibboleth_url, shibboleth_data);

# print('\nPosting shibboleth data to: '+shibboleth_url);
# print('Data:');
# print('\tRelayState:\t'+RelayState);
# print('\tSAMLResponse:\t<'+str(len(SAMLResponse))+'character long entry>');

# The response to the Shibboleth POST shuold redirect you to the original site
# you wanted to visit and the end result content should be that site
file=open('mytritonlink.html', 'w');
file.write(shibboleth_resp.content);
file.close();
