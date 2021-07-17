# Create an HTMLFile for parsing the audit
$html = New-Object -ComObject 'HTMLFile';
$html.write([ref]'');
$html.write([System.Text.Encoding]::Unicode.GetBytes($(Get-Content audit.html -Raw)));

# Begin scraping via the 'takenCourse' classname
# $headers links target rawData with childNode index under each element
$takenCourses = $html.GetElementsByClassName('takenCourse');
$headers = ('Term', 'Class', 'Credits', 'Grade');

# Data will be stored in PSCustomObject[] (using ArrayList for appending) 
$rawData = [System.Collections.ArrayList]::new();

# Iterate through each element, creating a new entry (PSCustomObject) for each course
$takenCourses | % {
    $course = $_;
    $entry = @{};

    # For each entry, iterate through headers to parse target data from each element
    $headers | % {
        $entry.Add($_, $course.childNodes[$headers.indexOf($_)].innerText);
    }

    # PSCustomObject has superior table display
    $entry = [pscustomobject]$entry;

    # Check for duplicates before appending, or just append if it's the first
    if (-not $rawData.Length -or -not $rawData.Class.Contains($entry.Class)) {
        $rawData.Add($entry);
    }
}

# Format the raw data by sorting with
# 1) Year
# 2) WI(nter) -> SP(ring) -> S(ummer) -> FA(ll)
# Then format the results to show Term, Grade, Class, and Credits in that order
# Finally, group by term for visual clarity
$formatted = $rawData | Sort-Object {
    $_.Term.Substring(2); 
    $(Switch -Regex ($_.Term) {
            'WI..' {1};
            'SP..' {2};
            'S[0-9]..' {3};
            'FA..' {4};
        })} | Format-Table -Property Term, Grade, Class, Credits -GroupBy Term;
