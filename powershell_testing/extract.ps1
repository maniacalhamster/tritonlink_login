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

# Setup another ArrayList of PSCustomObjects for requirements
$neededCourses = [System.Collections.ArrayList]::new(); 

# Iterate through all needed reqs, accessing title, count, notFrom, and course
# data via the parent element
$html.getElementsByClassName("subreqNeeds") | % { 
    $parent = $_.parentElement;
    $title = $parent.getElementsByClassName("subreqTitle")[0].innerText; 
    $count = $parent.getElementsByClassName("count number")[0].innerText;
    $notFrom = $parent.getElementsByClassName("notcourses")[0].innerText;
    $courses = $parent.getElementsByClassName("selectcourses")[0].innerText
        $neededCourses.Add([pscustomobject]@{
                "title" = $title;
                "count" = $count;
                "notFrom" = $notFrom;
                "courses" = $courses;
                })
}

# Additionally format the data to prioritize Courses over NotFrom
$neededCourses = $neededCourses | Format-Table -Property Title, Count, Courses, NotFrom
