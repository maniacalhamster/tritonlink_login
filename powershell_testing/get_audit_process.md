# Nicknames 

      - Login Names
name        | value 
:--         | :--
relaystate  | *target service url*
auth_one    | https://a5.ucsd.edu/tritON/profile/SAML2/Redirect/SSO?execution=e1s1
duo         | https://api-ce13a1a7.duosecurity.com/frame/web/v1/auth?tx=*[insert-tx-here]*
prompt      | https://api-ce13a1a7.duosecurity.com/frame/prompt
status      | https://api-ce13a1a7.duosecurity.com/frame/status
result      | https://api-ce13a1a7.duosecurity.com/frame/status/*[value here changes]*
auth_two    | https://a5.ucsd.edu/tritON/profile/SAML2/Redirect/SSO?execution=e1s2
shibboleth  | https://act.ucsd.edu/Shibboleth.sso/SAML2/POST

      - Generate Audit Names
name        | value
:--         | :--
list        | https://act.ucsd.edu/studentDarsSelfservice/audit/list.html
create      | https://act.ucsd.edu/studentDarsSelfservice/audit/create.html
reload      | https://act.ucsd.edu/studentDarsSelfservice/audit/list.html?autoPoll=true
read        | https://act.ucsd.edu/studentDarsSelfservice/audit/read.html?id=JobQueueRun!!!!*[value here changes]*

# Login Process
1) **GET** [relaystate](#Nicknames) `--[redirect]->` **GET** [auth_one](https://a5.ucsd.edu/tritON/profile/SAML2/Redirect/SSO?execution=e1s1)

2) **POST** [auth_one](https://a5.ucsd.edu/tritON/profile/SAML2/Redirect/SSO?execution=e1s1) `--[redirect]->` **GET** [auth_two](https://a5.ucsd.edu/tritON/profile/SAML2/Redirect/SSO?execution=e1s2)
   - Data: `{'urn:mace:ucsd.edu:sso:username'; 'urn:mace:ucsd.edu:sso:password'}`
   - Response: data containing **tx**
      - Used in the next step

3) **POST** [duo](https://api-ce13a1a7.duosecurity.com/frame/web/v1/auth?tx=*[insert-tx-here]*) `--[redirect]->` **GET** [prompt w/ sid](https://api-ce13a1a7.duosecurity.com/frame/prompt?sid=SID-provided-here)
   - Data: `{'tx'; 'parent'; 'referer'}`
   - Redirected: Url contains **sid** encoded as query param
      - Decoded **sid** used in the next step

4) **POST** [prompt](https://api-ce13a1a7.duosecurity.com/frame/prompt)
   - Data: `{'sid'; 'device'; 'factor'; 'dampen_choice'; 'out_of_date'; 'days_out_of_date'; 'days_to_block'}`
   - Response: data containing **txid**
      - Used in the next step

5) **POST** [status](https://api-ce13a1a7.duosecurity.com/frame/status)
   - Data: `{'sid'; 'txid'}`
   - Response 1: status message

6) **POST** [status](https://api-ce13a1a7.duosecurity.com/frame/status)
   - Data: `{'sid'; 'txid'}`
      - same data as above
   - Wait: User responds to push notification (until timeout)
   - Response: data containing [result](https://api-ce13a1a7.duosecurity.com/frame/status/value-here-changes) url for the next **POST**

7) **POST** [result](https://api-ce13a1a7.duosecurity.com/frame/status/value-here-changes)
   - Data: `{'sid'}`
   - Response: data containing `<AUTH>` portion of `sig_response`
      - also contains url encoded [auth_two] but we already have the original (from auth_one redirect)

8) **POST** [auth_two](https://a5.ucsd.edu/tritON/profile/SAML2/Redirect/SSO?execution=e1s2)
   - Data: `{'_eventId'; 'sig_response'}`
   - Response: data containing SAMLResponse
      - also contains partially hex encoded [relaystate] but we already have the original

9) **POST** [shibboleth](https://act.ucsd.edu/Shibboleth.sso/SAML2/POST) `--[redirect]->` **GET** [relaystate w/ crossApp](#Nicknames)
   - Data: `{'RelayState'; 'SAMLResponse}`
   - Note: `crossApp` string unknown for now
      - might be an encrypted value, like `SAMLResponse`?
   -  This is the end of the login process!

# Generate Audit Process
1) **GET**  [list](https://act.ucsd.edu/studentDarsSelfservice/audit/list.html)
   - primitive string selection used to find the first instance of read.html
      - first instance is latest created audit

2) **POST** [create](https://act.ucsd.edu/studentDarsSelfservice/audit/create.html) `--[redirect]->` **GET** [reload](https://act.ucsd.edu/studentDarsSelfservice/audit/list.html?autoPoll=true)
   - Data: `{'includeInProgressCourses'; 'includePlannedCourses'; 'sysIn.velsw'; 'auditTemplate'; 'sysIn.fdpmask'; 'useDefaultDegreePrograms'; 'pageRefresh'}`
   - **POST**ing preset data will generate a request for a new audit
   - redirected to the `[list w/ autoPoll=true]` AKA [reload](https://act.ucsd.edu/studentDarsSelfservice/audit/list.html?autoPoll=true) url

3) **GET** [reload](https://act.ucsd.edu/studentDarsSelfservice/audit/list.html?autoPoll=true)
   - Loop:
      - Read the first instance of `[read]` for latest audit
      - wait
      - **GET** again
   - Keep looping until new [read](https://act.ucsd.edu/studentDarsSelfservice/audit/read.html?id=JobQueueRun!!!!value-here-changes) url for audit is retrieved
      - This works for both empty and nonempty starting lists

4) **GET** [read](https://act.ucsd.edu/studentDarsSelfservice/audit/read.html?id=JobQueueRun!!!!value-here-changes)
   - finally can get a copy of the audit page 
   - stored in a local file called 'audit.html' for future parsing