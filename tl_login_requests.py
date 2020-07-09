import requests
import urllib
import re
from HTMLParser import HTMLParser;
from bs4 import BeautifulSoup

#UCSD SSO SAML Response Parser class
class UCSD_SSO_SAML_Parser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self);
        self.SAMLResponse = '';
        self.RelayState = '';
    def handle_starttag(self,tag,attrs):
        self.SAMLCatched = False;
        self.RelayStateCatched = False;
        for attr in attrs:
            if attr[0] == 'name':
                if attr[1] == 'RelayState':
                    self.RelayStateCatched = True;
            if self.RelayStateCatched:
                if attr[0] == 'value':
                    self.RelayState = attr[1];
        for attr in attrs:
            if attr[0] == 'name':
                if attr[1] == 'SAMLResponse':
                    self.SAMLCatched = True;
            if self.SAMLCatched:
                if attr[0] == 'value':
                    self.SAMLResponse = attr[1];
    def close(self):
        HTMLParser.close(self);

""" For simulating user login in UCSD Shibboleth SSO """
class TritonLink:
    tritonlink_url = "http://mytritonlink.ucsd.edu";
    ucsd_sso_saml_url = "https://act.ucsd.edu/Shibboleth.sso/SAML/POST";
    ucsd_sso_saml2_url = "https://act.ucsd.edu/Shibboleth.sso/SAML2/POST";
    def __init__(self,user_id,user_pd):
        self._requests_session = requests.Session();
        self._loggedin = False;
        self._tritonlink_username = user_id;
        self._tritonlink_password = user_pd;
        self._mytritonlink = None;
    
    @property
    def requests_session(self):
        return self._requests_session;

    @property
    def mytritonlink(self):
        return self._mytritonlink;

    """ 
    login(self)
    Return mytritonlink page response 
    """
    def login(self):
        if (self._loggedin):
            return True;
        response = self._requests_session.get(self.tritonlink_url, allow_redirects=False);
        student_sso_param = {
                'urn:mace:ucsd.edu:sso:username':self._tritonlink_username,
                'urn:mace:ucsd.edu:sso:password':self._tritonlink_password,
                '_eventId_proceed' : '',
                }

	# Updated to account for 2 factor authentication with Duo as of 2019/2020 vvvv
	# 	for more comments/explanations and print statements, take a look
	#	at tl_login.py! The code here has trimmed out a lot of what was
	#	found out to be unnecesarry in the authentication process

	while not (re.search('SAMLRequest', response.content)):
		response = self._requests_session.send(response.next, allow_redirects=False);
	RelayState = response.url;

	sso_es1 = self._requests_session.send(response.next);
	sso_es2 = self._requests_session.post(sso_es1.url, data=student_sso_param);

	data_host = re.search('(?<=data-host=").*com', sso_es2.content).group(0);
	data_sig_request = re.search('(?<=data-sig-request=").*==\|.{40}', sso_es2.content).group(0);

	tx = re.search('TX.*(?=:)', data_sig_request).group(0);
	parent = urllib.quote_plus(sso_es2.url);
	auth_url = 'https://'+data_host+'/frame/web/v1/auth?tx='+tx+'&parent='+parent+'&v=2.3';

	auth_data = {'tx':tx, 'parent':sso_es2.url, 'referer':sso_es2.url, 'java_version':'', 'flash_version':'',
	'screen_resolution_width':'1536', 'screen_resolution_height':'864', 'color_depth':'24',
	'is_cef_browser':'false', 'is_ipad_os':'false'};

	self._requests_session.headers['User-Agent']='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/83.0.4103.116';
	prompt = self._requests_session.post(auth_url, data={});

	prompt_url = re.search('.*(?=\?sid)',prompt.url).group(0);
	sid = re.search('(?<=sid=).*',urllib.unquote(prompt.url)).group(0);
	prompt_data = {'sid':sid, 'device':'phone1', 'factor':'Duo Push'};
	prompt_resp = self._requests_session.post(prompt_url, prompt_data);
	print(prompt_resp.content);

	status_url = re.search('.*(?=prompt)', prompt_url).group(0) + 'status';
	txid = re.search('(?<=txid": ").*-.{12}', prompt_resp.content).group(0);
	status_data = {'sid':sid, 'txid':txid};
	status_resp = self._requests_session.post(status_url, status_data);
	print(status_resp.content);

	status_resp = self._requests_session.post(status_url, status_data);
	print(status_resp.content);

	result_url = status_url + '/' + txid;
	result_data = {'sid':sid};
	result_resp = self._requests_session.post(result_url, result_data);

	duo_url = sso_es2.url;
	sig_response = re.search('AUTH.*==\|.{40}', result_resp.content).group(0);
	sig_response = sig_response+re.search(':APP.*', data_sig_request).group(0);
	duo_data = {'_eventId':'proceed', 'sig_response':sig_response};
	duo_resp = self._requests_session.post(duo_url, duo_data);

	# Not sure how to use HTMLParser, just used regex to find SAMLResponse
	SAMLResponse = re.search('(?<=SAMLResponse" value=").*(?="/>)', duo_resp.content).group(0);

	# End of changeups to code to account for 2 factor authentication ^^^^^^^^^^^^^

        SAML_param = {
                'RelayState' : RelayState,
                'SAMLResponse' : SAMLResponse,
                }

        #update to SAML2, SPRING 2015
        shib_resp = self._requests_session.post(
                self.ucsd_sso_saml2_url,SAML_param,allow_redirects = False);
        response = self._requests_session.get(RelayState);
        # ::TODO need to check the validity of login
        self._loggedin = True;
        self._mytritonlink = response.text;
        return True;

    def get_student_info(self):
        if (not(self._loggedin)):
            return False;
        soup = BeautifulSoup(self._mytritonlink, 'lxml');
        sidebar = soup.find('div',id='my_tritonlink_sidebar')
        name = sidebar.h2.string.strip()
        college = sidebar.find_all('p')[0].a.string.strip();
        major = sidebar.find_all('p')[1].a.string.strip();
        years = sidebar.find_all('p')[2].b.string.strip()
        account_balance = soup.find(
                'div',id='account_balance'
                ).find(
                        'div','cs_box_amount'
                        ).strong.string.strip();
        holds = soup.find(
                'div',id='holds'
                ).find(
                        'div','cs_box_content'
                        ).p.string.strip();
        holds = re.findall(r'\b\d+\b',holds)[0];
        student_info = {
                'name' : name,
                'college' : college,
                'major' : major,
                'years' : years,
                'account_balance':account_balance,
                'holds':holds,
                };
        return student_info;

    def get_courses_enrolled(self):
        enrolled_courses_url = "https://act.ucsd.edu/studentEnrolledClasses/enrolledclasses"
        enrolled_classes_html = self._requests_session.get(enrolled_courses_url);
        soup = BeautifulSoup(enrolled_classes_html.text, 'lxml');
        quarters = {};
        courses_html = soup.find_all('td',{'bgcolor':'#c0c0c0'});
        #find all quarters first
        quarters_html = courses_html[len(courses_html)-1].find_all_previous('td',{'width':'34%','class':'boldheadertxt_noborder'})
        for quarter_html in quarters_html:
            quarter_name = quarter_html.text.strip();
            quarters[quarter_name] = [];

        courses = [];
        for course_html in courses_html:
            course_quarter = course_html.find_previous('td',{'width':'34%','class':'boldheadertxt_noborder'}).text.strip();
            
            course_row = course_html.find_next('tr')
    
            course_department = course_row.find_all('td')[1].text;
            course_section = course_row.find_all('td')[2].text;
            course_title = course_row.find_all('td')[3].text;
            course_units = course_row.find_all('td')[4].text;
            course_grading = course_row.find_all('td')[5].font.text;
            course_instructor = course_row.find_all('td')[6].text;
            
            meetings_html = course_row.find_all_next('tr',class_=re.compile("white_background"))

            meetings = []
            for meeting_html in meetings_html:
                terminating = False;
                attrs_next = meeting_html.find_next('tr').attrs
                if ((not('class' in attrs_next)) and (attrs_next)):
                    #terminating, but we still want this meeting row
                    terminating = True;

                meeting_row = meeting_html.find_all_next('td')
                meeting_id = meeting_row[0].text.strip();              
                meeting_type = meeting_row[1].text.strip();              
                meeting_section = meeting_row[2].text.strip();              
                meeting_time = meeting_row[3].text.strip();              
                meeting_days = meeting_row[4].text.strip();              
                meeting_building = meeting_row[5].text.strip();
                meeting_room = meeting_row[6].text.strip();

                meeting = {
                        'id' : meeting_id,
                        'type' : meeting_type,
                        'section' : meeting_section,
                        'time' : meeting_time,
                        'days' : meeting_days,
                        'building' : meeting_building,
                        'room' : meeting_room
                        };
                meetings.append(meeting);
                if terminating:
                    break;

            course = {
                    'department' : course_department,
                    'section' : course_section,
                    'title' : course_title,
                    'units' : course_units,
                    'grading' : course_grading,
                    'instructor' : course_instructor,
                    'meeting' : meetings
                    };
            courses = quarters[course_quarter]
            courses.append(course);
            quarters[course_quarter] = courses;
        return quarters;

    def get_courses_schedule(self):
        return 0;
