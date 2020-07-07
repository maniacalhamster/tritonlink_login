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
RelayState = 'https://act.ucsd.edu/studentDarsSelfservice';

# initial response to get request for site will be a redirection with some data
resp = login.get(RelayState, allow_redirects=False);
url = re.search('https.*service', resp.content).group(0);
SAMLRequest = re.search('(?<=SAMLRequest=).*(?=&amp;)', resp.content).group(0);
RelayState_encoded = re.search('(?<=RelayState=).*service', resp.content).group(0);

# first redirect takes you to sso page with <samlrequest> & <relaystate> query strings
# this site will set some cookies <jsessionid>, <randomhash?>, and redirect you again
sso_saml = login.send(resp.next, allow_redirects=False);

# second redirect takes you to the part A of signing in (user credentials)
# page has a POST form to be filled out with user data and sent to itself
sso_es1 = login.send(sso_saml.next);

# POST form contents are PID, password, and eventId (not sure what this is for)
# POST request sent to self will return a redirect to part B of signing in (DUO) 
login_data = {'urn:mace:ucsd.edu:sso:username':pid, 'urn:mace:ucsd.edu:sso:password':pwd, '_eventId':'proceed'};
sso_es2 = login.post(sso_es1.url, data=login_data);

# POST form contents for the Duo part of signing in is given here but the current
# sig_request is only the <tx> value and not the true sig_request value
data_host = re.search('(?<=data-host=").*com', sso_es2.content).group(0);
data_sig_request = re.search('(?<=data-sig-request=").*==\|.{40}', sso_es2.content).group(0);
data_post_action = re.search('(?<=data-post-action=").*e\d+s\d+', sso_es2.content).group(0);

# first, you must complete the duo authentication process, which starts with a
# POST request to the above host name's /frame/web/v1/auth? site with the
# <tx>, <parent>, and <v> query strings (tx is the 'TX portion' of the sig_request from before)
tx = re.search('TX.*(?=:)', data_sig_request).group(0);
parent = urllib.quote_plus(sso_es2.url);
v = '2.3';
auth = 'https://'+data_host+'/frame/web/v1/auth?tx='+tx+'&parent='+parent+'&v='+v;
# POST form data for the request to this url will hold the following data:
auth_data = {'tx':tx, 'parent':sso_es2.url, 'referer':sso_es2.url, 'java_version':'', 'flash_version':'', 
	'screen_resolution_width':'1536', 'screen_resolution_height':'864', 'color_depth':'24',
	'is_cef_browser':'false', 'is_ipad_os':'false'};
# Requires User-Agent and Referer headers to be manually set first
login.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36 Edg/83.0.478.58';
login.headers['Referer'] = auth;
# POST request sent will return a redirect to generate a duo authenticate prompt
# response should also set a cookie 
prompt = login.post(auth, data=auth_data);

# POST request to the prompt_url with the following form data will send a push
# notification to the listed device
prompt_url = re.search('.*(?=\?sid)',prompt.url).group(0);
sid = re.search('(?<=sid=).*',urllib.unquote(prompt.url)).group(0)
prompt_data = {'sid':sid, 'device':'phone1', 'factor':'Duo Push', 'out_of_data':'',
		'days_out_of_data':'', 'days_to_block':'None'};
prompt_resp = login.post(prompt_url, prompt_data);

# response to the prompt POST will hold a txid needed for the next POST for status
# status POST sent twice, first to check if prompt sent succesfully and the 
# second waits until either user responds on device or timeout occurs
status_url = re.search('.*(?=prompt)', prompt_url).group(0) + 'status';
txid = re.search('(?<=txid": ").*-.{12}', prompt_resp.content).group(0);
status_data = {'sid':sid, 'txid':txid};
status_resp = login.post(status_url, status_data);

# upon user approval on their device, the second status POST response will set 
# another cookie and provide a resulting url to send the next POST
status_resp = login.post(status_url, status_data);

# result_url given in the response of second status post is a lot more work to 
# parse than just adding the txid to the status url (which it is)
result_url = status_url + '/' + txid;
result_data = {'sid':sid};
result_resp = login.post(result_url, result_data);

# request header referer changes back to the original duo page url
login.headers['Referer'] = sso_es2.url;

# The content of this POST to the result url holds the true sig_response needed
# to finally fill the POST form for part B (DUO) in signing in 
duo_url = sso_es2.url;
sig_response = re.search('AUTH.*==\|.{40}', result_resp.content).group(0);
sig_response = sig_response+re.search(':APP.*(?=")', sso_es2.content).group(0);
duo_data = {'_eventId':'proceed', 'sig_response':sig_response};
duo_resp = login.post(duo_url, duo_data);

# After succesfully completing 2 factor authentication, you are finally given 
# the SAMLResponse (the long successful one!) and can make the FINAL POST to
# the shibboleth url with both RelayState (original site) and SAMLResponse
shibboleth_url = 'https://act.ucsd.edu/Shibboleth.sso/SAML2/POST';
SAMLResponse = re.search('(?<=SAMLResponse" value=").*(?="/>)', duo_resp.content).group(0);
shibboleth_data = {'RelayState':RelayState, 'SAMLResponse':SAMLResponse};
shibboleth_resp = login.post(shibboleth_url, shibboleth_data);

# The response to the Shibboleth POST shuold redirect you to the original site
# you wanted to visit and the end result content should be that site
final = shibboleth_resp;

print(final.content);
