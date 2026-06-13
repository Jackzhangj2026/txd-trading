with open('blog/index.html', 'r') as f:
    content = f.read()

# Replace the corrupted section
old_section = '''    tags: ["corrugated plastic", "logistics", "packaging comparison", "ROI analysis"]
  {
    title: "PP Hollow Sheet Applications in Automotive Packaging",
    date: "2026-06-07",
    url: "pp-hollow-sheet-applications-automotive-packaging.html",
    excerpt: "A comprehensive guide to PP hollow sheet applications in automotive packaging — covering EV battery module trays and returnable container systems to JIT delivery dunnage and lightweighting strategies for modern automotive supply chains.",
    tags: ["automotive packaging", "EV batteries", "returnable systems", "lightweighting"]
  },
  },
];'''

new_section = '''    tags: ["corrugated plastic", "logistics", "packaging comparison", "ROI analysis"]
  },
  {
    title: "PP Hollow Sheet Applications in Automotive Packaging",
    date: "2026-06-07",
    url: "pp-hollow-sheet-applications-automotive-packaging.html",
    excerpt: "A comprehensive guide to PP hollow sheet applications in automotive packaging — covering EV battery module trays and returnable container systems to JIT delivery dunnage and lightweighting strategies for modern automotive supply chains.",
    tags: ["automotive packaging", "EV batteries", "returnable systems", "lightweighting"]
  },
];'''

if old_section in content:
    content = content.replace(old_section, new_section)
    with open('blog/index.html', 'w') as f:
        f.write(content)
    print("Fixed successfully!")
else:
    print("Could not find the exact text to replace")
    # Show what's around the area
    import re
    m = re.search(r'corrugated plastic.*?ROI analysis.*?\]', content, re.DOTALL)
    if m:
        print("Found near:", repr(m.group()))
