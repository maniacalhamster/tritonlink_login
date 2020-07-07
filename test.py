# --------------------------------------------------------------------------------
#		FLAWED UNDERSTANDING OF LOGIN PROCESS
#
# This file was created during my first run through of the login process and served
# mainly as a way to save progress / run batches of requests at once rather than
# typing everything out in a python console.
# Started using workaround about halfway through the requests and ended up with
# an SAMLResponse encoding Auth Failure
# A fresh start attempting to abide by the requests sent in browser as closely
# as possible can be found in the new audit_login.py (that one works!)
#
#		FLAWED UNDERSTANDING OF LOGIN PROCESS
# ---------------------------------------------------------------------------------
import requests
import re
import getpass

# start a requests session to save data between requests
# target for test is the student degree audit page
login = requests.Session();
RelayState = 'https://act.ucsd.edu/studentDarsSelfservice';

resp = login.get(RelayState);
print("Redirected to "+resp.url);

uname = raw_input("Enter your ID: ");
password = getpass.getpass("Enter your password: ");

# filling in user credentials with post form to first layer of authentication
resp = login.post(resp.url, data={'urn:mace:ucsd.edu:sso:username':uname,'urn:mace:ucsd.edu:sso:password':password,'_eventId_proceed':''});

# scrounging through results for duo ticket and encoded parent url
tx = re.search('TX.*(?=:)', resp.content).group(0);
parent = 'https%3A%2F%2Fa5.ucsd.edu%2FtritON%2Fprofile%2FSAML2%2FRedirect%2FSSO%3Fexecution'+re.search('e\d+s\d+', resp.content).group(0)+'%3D';

# javascript portion of duo page done manually with set duo host
duo = 'https://'+re.search('api.*com', resp.content).group(0);

# source = resp.url;
# resp = login.get(duo);
#resp = login.post(duo, data={'tx':tx, 'parent':source, 'referer':source});

# empty post to duo host with ticket and parent url in query strings
resp = login.post(duo+'/frame/web/v1/auth?'+'tx='+tx+'&parent='+parent+'&v=2.3');

# scrounging through results for security ID 
sid = re.search('(?<=sid=).*', resp.url).group(0);

# filling out a post form asking for push notification to the phone
resp = login.post(resp.url, data={'device':'phone1', 'factor':'Duo Push'});
print(resp.url + '\n' + resp.content+'\n');

# scrounge the results for the ticket ID
txid = re.search('(?<=txid": ").*-.{12}', resp.content).group(0);

# filling out a post to check for status of the push request
status = login.post(duo+'/frame/status?sid='+sid, data={'txid': txid}); 
print(status.url + '\n' + status.content + '\n');

# second post waits for user to respond untill timeout
status = login.post(duo+'/frame/status?sid='+sid, data={'txid':txid});
print(status.url + '\n' + status.content + '\n');

# filling out the post to get the sig_response needed in the next post
status = login.post(duo+'/frame/status/'+txid+'?sid='+sid, data={'txid':txid});
print(status.url + '\n' + status.content + '\n');

# finally you can fill out the POST form for e?s2 (last layer of authentication)
# host = re.search('https://.*s.\=', status.content).group(0);
	# turns out the '=' was  in the wrong place
	#  B  R  U  H
host = re.search('https://.*(?=e\d+s\d+)', status.content).group(0)+'='+re.search('e\d+s\d+(?=\=)', status.content).group(0);
sig_response = re.search('AUTH.*==\|.{40}', status.content).group(0);

resp = login.post(host, data={'_eventId':'proceed', 'sig_response':sig_response});

SAMLResponse = re.search('(?<=SAMLResponse" value=").*(?=")', resp.content).group(0);

resp = login.post('https://act.ucsd.edu/Shibboleth.sso/SAML2/POST', data={'RelayState':RelayState, 'SAMLResponse':SAMLResponse});

