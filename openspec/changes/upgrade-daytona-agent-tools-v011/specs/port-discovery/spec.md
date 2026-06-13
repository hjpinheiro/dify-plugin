## ADDED Requirements

### Requirement: Automatic web port discovery and exposure

The provider SHALL offer an `auto_expose` tool that scans the sandbox for
listening TCP ports and auto-generates preview URLs with proxy-domain rewriting.

#### Scenario: Single web server running

- GIVEN a sandbox has a Flask server listening on port 5000
- WHEN `auto_expose` is called
- THEN the tool SHALL detect port 5000
- AND SHALL generate a preview URL with proxy rewriting
- AND the response SHALL include `{port: 5000, url: "https://..."}`

#### Scenario: No servers running

- GIVEN a sandbox has no listening ports in range 1000-10000
- WHEN `auto_expose` is called
- THEN the tool SHALL return an empty ports array
- AND the text message SHALL say no services were detected

#### Scenario: Multiple servers running

- GIVEN ports 3000 and 8000 are listening
- WHEN `auto_expose` is called
- THEN the tool SHALL detect both ports
- AND SHALL return preview URLs for each

#### Scenario: Proxy domain configured

- GIVEN `preview_proxy_domain` credential is set
- WHEN `auto_expose` generates URLs
- THEN each URL SHALL be rewritten through the proxy domain
- AND SHALL NOT use the raw Daytona proxy URL
