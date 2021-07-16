# Helper function to get user login credentials
function get_creds()
{
    $datafile = "login.json";

    if(!(Test-Path $datafile)){
        $data = @{username='';password=''};

        $username = Read-Host -Prompt "Username" | ConvertTo-SecureString -AsPlainText;
        $password = Read-Host -Prompt "Password" -AsSecureString;

        @{
            username=$username | ConvertFrom-SecureString;
            password=$password | ConvertFrom-SecureString;
        } | ConvertTo-Json > $datafile;

        $username = $username | ConvertFrom-SecureString -AsPlainText;
        $password = $password | ConvertFrom-SecureString -AsPlainText;
    }

    else{
        $data = Get-Content $datafile | ConvertFrom-Json;

        $username = $data.username | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText;
        $password = $data.password | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText;
    }

    $data.username = [System.Uri]::EscapeDataString($username);
    $data.password = $password;

    return $data;
}

# Helper function to url-encode
function encode($inp)
{
    Write-Host -ForegroundColor Yellow "Encoding: $inp";
    return [System.Web.HttpUtility]::UrlEncode($inp);
}

# Helper function to url-decode
function decode($inp)
{
    Write-Host -ForegroundColor Yellow "Decoding: $inp";
    return [System.Web.HttpUtility]::UrlDecode($inp);
}

# Helper function to make POST requests
function POST($url, $session, $body)
{
    Write-Host ("POST to:`t{0}" -f $url);
    return Invoke-WebRequest -UseBasicParsing -Uri $url -WebSession $session -Method POST -Body $body; 
}

# Helper function to make GET requests
function GET($url, $session)
{
    Write-Host ("GET from:`t{0}" -f $url);
    return Invoke-WebRequest -UseBasicParsing -Uri $url -WebSession $session;
}

# Helper function to get Request URI from Reponse 
function getAbsoluteUri($response)
{
    if((Get-Host).Version.Major -eq 5){
        return $response.BaseResponse.ResponseUri.AbsoluteUri;
    } else {
        return $response.BaseResponse.RequestMessage.RequestUri.AbsoluteUri;
    }
}

# Audit url is target, want to get to degree audit page 
# a basic get request redirects you to the beginning of the authorization process
$audit_url = "https://act.ucsd.edu/studentDarsSelfservice";
$audit_resp = Invoke-WebRequest -UseBasicParsing -Uri $audit_url -SessionVariable session;

# Part A of signing in is just a POST form for user login data 
$auth_one_url = getAbsoluteUri $audit_resp;

if((Get-Host).Version.Major -ne 5)
{
    $data = get_creds;
}
else
{
    $data = @{
        'username'=Read-Host("username");
        'password'=Read-Host("password")};
}

$auth_one_data= @{
    'urn:mace:ucsd.edu:sso:username'=$data.username;
    'urn:mace:ucsd.edu:sso:password'=$data.password;
    '_eventId_proceed'=''};
$auth_one_resp = POST $auth_one_url $session $auth_one_data;

# Sucessful POST will redirect to part B of signing in (DUO)
# contents hold info used to generate URI and data to POST
# the current sig_request contains the <APP> part of the full sig_response
$content    = $auth_one_resp.Content;
$data_host  = ($content | Select-String "(?<=data-host=`").*.com").Matches.Value;
$data_sig_request = ($content | Select-String "(?<=data-sig-request=`").*(?=`")").Matches.Value;
$data_post_action = ($content | Select-String "(?<=data-post-action=`").*(?=`")").Matches.Value

# Part B.1.1: generate the URI that form data will be POSTed to 
$tx         = ($data_sig_request | Select-String "TX.*(?=:)").Matches.Value;
$parent     = encode($data_post_action);
$version    = "2.3";

$duo_url = 'https://{0}/frame/web/v1/auth?tx={1}&parent={2}&v={3}';
$duo_url = $duo_url -f $data_host, $tx, $parent, $version;

# Part B.1.2: generate the form data that will POSTed to the above URI and send
$duo_data  = @{
    'tx'        = $tx;
    'parent'    = $parent;
    'referer'   = $parent};
$duo_resp = POST $duo_url $session $duo_data;

# Part B.2.1: generate URI and form data to begin a 3 part POST process
# First POST (prompt) sends a Duo Push request to target device
$prompt_url = (getAbsoluteUri $duo_resp) -split "?sid=", 2, "SimpleMatch";
$sid        = decode($prompt_url[1]);
$prompt_url = $prompt_url[0];
$prompt_data    = @{
    'sid'       = $sid;
    'device'    = 'phone1';
    'factor'    = 'Duo Push';
    'dampen_choice'     = 'true';
    'out_of_date'       = '';
    'days_out_of_date'  = '';
    'days_to_block'     = 'None'};
$prompt_resp = POST $prompt_url $session $prompt_data;

# Prompt response holds txid needed for status POSTs
# onSuccess, returns sid and txid 
# onFailure, notifies user of apparent issue and exits script
$content    = $prompt_resp.Content | ConvertFrom-Json;
$status     = $content.stat;
if (!$status){
    return "Issue with sending Duo Push prompt";
}
$txid = $content.response.txid;
$status_url = $prompt_url -replace "prompt","status";
$status_data    = @{
    'sid'   = $sid;
    'txid'  = $txid};

# Part B.2.2: Second POST (status) checks if prompt was successful
# onSuccess, nothing special just continues the script
# onFailure, notifies user of apparent issue and exits script
$status_resp    = POST $status_url $session $status_data;
$content    = $status_resp.Content | ConvertFrom-Json;
$status     = $content.stat;
if (!$status){
    return "Issue with checking on Duo Push status";
}
Write-Host -ForegroundColor Green $content.response.status;

# Part B.2.3: Third POST (status) waits until user responds on device (until timeout)
# onSucess, returns a result URL to make an extra fourth POST to
# onFailure, notifies user of timeout and exits script
$status_resp = POST $status_url $session $status_data;
$content    = $status_resp.Content | ConvertFrom-Json;
$status     = $content.stat;
if ($status -ne "OK"){
    return $content.response.status;
}
Write-Host -ForegroundColor Green $content.response.status;

# Part B.2.4: Fourth POST (special status) 
# retreives the <AUTH> portion to complete sig_response 
$result_url = $status_url -replace "/frame/status", ($status_resp.content | ConvertFrom-Json).response.result_url;
$result_data = @{'sid'=$sid};
$result_resp = POST $result_url $session $result_data;

# <AUTH> and <APP> portions of sig_response combined, used alongside _eventID
# Part B.3.1: Can finally make a POST request to finish the (DUO) portion of 2FA
$auth_two_url   = getAbsoluteUri $auth_one_resp;
$sig_response   = "{0}:{1}" -f ($result_resp.Content | ConvertFrom-Json).response.cookie, ($data_sig_request -replace ".*:");
$auth_two_data  = @{
    '_eventId'      = 'proceed';
    'sig_response'  = $sig_response};
$auth_two_resp  = POST $auth_two_url $session $auth_two_data;

# SAMLResponse is finally returned after completing Two-Factor Auth
# use it to make a final POST to shibboleth url along w/ RelayState (target url)
$saml_response  = $auth_two_resp.InputFields.Find("SAMLResponse").Value;
$shibboleth_url = "https://act.ucsd.edu/Shibboleth.sso/SAML2/POST";
$shibboleth_data = @{
    'RelayState'    = $audit_url;
    'SAMLResponse'  = $saml_response};
$shibboleth_resp = POST $shibboleth_url $session $shibboleth_data;

# Finally can navigate to list of available audits and select one to view
$list_url   = "{0}/audit/list.html" -f $audit_url;
$list_resp  = GET $list_url $session;

# Set read_link to first listed audit (automatically most recent)
# create a new audit for fresh results and continue to check against above
# read_link until new read_link found (compare against empty if no audits listed)
$old_read_link  = ($list_resp.Content | Select-String "(?<=href=`").*read.html.*(?=`")").Matches.Value;
$create_url     = "{0}/audit/create.html" -f $audit_url;
$create_data    = @{
    "includeInProgressCourses"  ='true';
    'includePlannedCourses'     ='';
    'sysIn.evalsw'              ='S';
    'auditTemplate'             ='htm!!!!htm';
    'sysIn.fdpmask'             ='';
    'useDefaultDegreePrograms'  ='true';
    'pageRefresh'               ='false'};
$create_resp = POST $create_url $session $create_data;
$reload_url = getAbsoluteUri $create_resp;
do{
    $reload_resp = GET $reload_url $session;
    $read_link = ($reload_resp.Content | Select-String "(?<=href=`").*read.html.*(?=`")").Matches.Value;
    Start-Sleep 1;
} while($old_read_link -eq $read_link);

# Can then use the read url to GET contents of the audit and save to file :)
$read_url = "{0}/audit/{1}" -f $audit_url, $read_link;
$read_resp = GET $read_url $session;
$read_resp.Content > audit.html;
