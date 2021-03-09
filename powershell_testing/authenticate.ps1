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
    Write-Host "Encoding: $inp";
    return [System.Web.HttpUtility]::UrlEncode($inp);
}

# Helper function to url-decode
function decode($inp)
{
    Write-Host "Decoding: $inp";
    return [System.Web.HttpUtility]::UrlDecode($inp);
}

# Helper function to make POST requests
function POST($url, $session, $body)
{
    Write-Host ("POST to: {0}" -f $url);
    return Invoke-WebRequest -UseBasicParsing -Uri $url -WebSession $session -Method POST -Body $body; 
}

# Audit url is target, want to get to degree audit page 
# a basic get request redirects you to the beginning of the authorization process
$audit_url = "https://act.ucsd.edu/studentDarsSelfservice";
$audit_resp = Invoke-WebRequest -UseBasicParsing -Uri $audit_url -SessionVariable session;

# Part A of signing in is just a POST form for user login data 
# helper function used to speed up the process
if((Get-Host).Version.Major -ne 5){
    $auth_one_url = $audit_resp.BaseResponse.RequestMessage.RequestUri.AbsoluteUri;
}
else{
    $auth_one_url = $audit_resp.BaseResponse.ResponseUri.AbsoluteUri;
}

if((Get-Host).Version.Major -ne 5){
    $data = get_creds;
}
else{
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
# contents to fill POST form for Duo part of signing in is given here however,
# the current sig_request is only the <APP> part and not the full sig_response
$content    = $auth_one_resp.Content;
$data_host  = ($content | Select-String "(?<=data-host=`").*.com").Matches.Value;
$data_sig_request = ($content | Select-String "(?<=data-sig-request=`").*(?=`")").Matches.Value;
$data_post_action = ($content | Select-String "(?<=data-post-action=`").*(?=`")").Matches.Value

# Part B.1.1: generate the URI that form data will be POSTed to 
$tx         = ($data_sig_request | Select-String "TX.*(?=:)").Matches.Value;
$parent     = encode($data_post_action);
$version    = "2.3";

$auth_two_url = 'https://{0}/frame/web/v1/auth?tx={1}&parent={2}&v={3}';
$auth_two_url = $auth_two_url -f $data_host, $tx, $parent, $version;

# Part B.1.2: generate the form data that will POSTed to the above URI and send
$auth_two_data  = @{
    'tx'        = $tx;
    'parent'    = $parent;
    'referer'   = $parent};
$auth_two_resp = POST $auth_two_url $session $auth_two_data;

# Part B.2.1: generate URI and form data to begin a 3 part POST process
# First POST (prompt) sends a Duo Push request to target device
if((Get-Host).Version.Major -ne 5){
    $prompt_url = ($auth_two_resp.BaseResponse.RequestMessage.RequestUri.AbsoluteUri).Split("?sid=");
} else {
    $prompt_url = $auth_two_resp.BaseResponse.ResponseUri.AbsoluteUri -split "?sid=", 2, "SimpleMatch";
}
$sid        = decode($prompt_url[1]);
$prompt_url = $prompt_url[0];
$prompt_data    = @{
    'sid'       = $sid;
    'device'    = 'phone1';
    'factor'    = 'Duo Push';
    'out_of_date'       = '';
    'days_out_of_date'  = '';
    'days_to_block'     = 'None'};
$prompt_resp = POST $prompt_url $session $prompt_data;

# Prompt response holds txid needed for status POSTs
$content    = $prompt_resp.Content | ConvertFrom-Json;
$status     = $content.stat;
if (!$status){
    return "Issue with sending Duo Push prompt";
}
$txid = $content.response.txid;

# Second POST (status) checks if prompt was successful
$status_url = $prompt_url -replace "prompt","status";
$status_data    = @{
    'sid'   = $sid;
    'txid'  = $txid};
$status_resp    = POST $status_url $session $status_data;

# Third POST (status) waits until user responds on device (or until timeout)
# returning a result URL to make an extra fourth POST to
$content    = $status_resp.Content | ConvertFrom-Json;
$status     = $content.stat;
if (!$status){
    return "Issue with checking on Duo Push status";
}
$status     = $content.response.status;
Write-Host $status;
$status_resp = POST $status_url $session $status_data;

# Fourth POST (special status) retreives the <AUTH> portion to complete sig_response
$result_url = $status_url -replace "/frame/status", ($status_resp.content | ConvertFrom-Json).response.result_url;
$result_data = @{'sid'=$sid};
$result_resp = POST $result_url $session $result_data;

# Both parts of sig_reponse are combined, and Referer set to original duo page url
# before sending the POST
if((Get-Host).Version.Major -ne 5){
    $duo_url = $auth_one_resp.BaseResponse.RequestMessage.RequestUri.AbsoluteUri;
} else {
    $duo_url = $auth_one_resp.BaseResponse.ResponseUri.AbsoluteUri;
}
$sig_response = "{0}:{1}" -f ($result_resp.Content | ConvertFrom-Json).response.cookie, ($data_sig_request -replace ".*:");
$duo_data = @{
    '_eventId' = 'proceed';
    'sig_response' = $sig_response};
$duo_resp = POST $duo_url $session $duo_data;

# SAMLResponse is finally returned after completing Two-Factor Auth
# use it to make a final POST to shibboleth url along w/ RelayState (target url)
$saml_response = $duo_resp.InputFields.Find("SAMLResponse").Value;
$shibboleth_url = "https://act.ucsd.edu/Shibboleth.sso/SAML2/POST";
$shibboleth_data = @{
    'RelayState' = $audit_url;
    'SAMLResponse' = $saml_response};
$shibboleth_resp = POST $shibboleth_url $session $shibboleth_data;
