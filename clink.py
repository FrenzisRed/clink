#!/usr/bin/env python3
# -----------------------------------------------------------
# Spider Comment Crawler
# Original author: FrenzisRed
# Modified with:
#   - recursion (-r) with domain restriction
#   - optional comment search (-c)
#   - pattern search (-w)
#   - link listing (-l), grouped internal vs external
#   - result saving (-s)
#   - deduplication of comments
#   - default to comments if no -c or -w
#   - highlighting of pattern matches
#   - BFS crawl with max depth (-d)
#   - unified link collection (no duplication)
# -----------------------------------------------------------

import sys
import re
from collections import deque
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup, Comment

print(r"""
 ______     __         __     __   __     __  __
/\  ___\   /\ \       /\ \   /\ "-.\ \   /\ \/ /
\ \ \____  \ \ \____  \ \ \  \ \ \-.  \  \ \  _"-.
 \ \_____\  \ \_____\  \ \_\  \ \_\\"\_\  \ \_\ \_\
  \/_____/   \/_____/   \/_/   \/_/ \/_/   \/_/\/_/

                ______     ______     ______     __     __     __         ______     ______
               /\  ___\   /\  == \   /\  __ \   /\ \  _ \ \   /\ \       /\  ___\   /\  == \
               \ \ \____  \ \  __<   \ \  __ \  \ \ \/ ".\ \  \ \ \____  \ \  __\   \ \  __<
                \ \_____\  \ \_\ \_\  \ \_\ \_\  \ \__/".~\_\  \ \_____\  \ \_____\  \ \_\ \_\
                 \/_____/   \/_/ /_/   \/_/\/_/   \/_/   \/_/   \/_____/   \/_____/   \/_/ /_/
                                                                                               v2.1
""")

class Crawler:
    def __init__(self, base_url, recurse=False, pattern=None, savefile=None, max_depth=None):
        self.base_url = base_url
        self.base_domain = urlparse(base_url).netloc
        self.recurse = recurse
        self.pattern = pattern
        self.savefile = savefile
        self.max_depth = max_depth
        self.comments = False
        self.links = False
        self.visited = set()
        self.results = {}

    def fetch(self, url):
        try:
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=10) as resp:
                return resp.read()
        except Exception as e:
            print(f"[!] Failed to fetch {url}: {e}")
            return None

    def parse(self, html, url):
        """Parse page HTML. Returns (soup, internal_links, external_links)."""
        soup = BeautifulSoup(html, 'html.parser')

        # Collect comments (deduplicated)
        comments = []
        if self.comments:
            found = [str(c) for c in soup.find_all(string=lambda text: isinstance(text, Comment))]
            seen = set()
            comments = [c for c in found if not (c in seen or seen.add(c))]

        # Collect pattern matches with highlighting
        matches = []
        if self.pattern:
            try:
                text = html.decode(errors='ignore')
                regex = re.compile(self.pattern, re.IGNORECASE)
                for line in text.splitlines():
                    if regex.search(line):
                        highlighted = regex.sub(lambda m: f">>>{m.group(0)}<<<", line.strip())
                        if highlighted not in matches:
                            matches.append(highlighted)
            except Exception as e:
                print(f"[!] Pattern search failed on {url}: {e}")

        # Collect all links once — reused for both reporting and recursion
        internal_links = []
        external_links = []
        for a in soup.find_all('a', href=True):
            link = urljoin(url, a['href']).split('#')[0]
            parsed = urlparse(link)
            if parsed.scheme in ('http', 'https'):
                if parsed.netloc == self.base_domain:
                    if link not in internal_links:
                        internal_links.append(link)
                else:
                    if link not in external_links:
                        external_links.append(link)

        self.results[url] = {
            'comments': comments,
            'matches': matches,
            'internal_links': internal_links if self.links else [],
            'external_links': external_links if self.links else [],
        }

        return soup, internal_links

    def crawl(self, start_url):
        """BFS crawl. Respects max_depth if set."""
        # Queue entries: (url, depth)
        queue = deque([(start_url, 0)])
        self.visited.add(start_url)

        while queue:
            url, depth = queue.popleft()
            print(f"[+] Crawling (depth {depth}): {url}")

            html = self.fetch(url)
            if not html:
                continue

            _, internal_links = self.parse(html, url)

            if self.recurse:
                if self.max_depth is None or depth < self.max_depth:
                    for link in internal_links:
                        if link not in self.visited:
                            self.visited.add(link)
                            queue.append((link, depth + 1))

    def report(self):
        out = []
        all_internal = set()
        all_external = set()

        for url, data in self.results.items():
            out.append(f"--- Page: {url} ---")
            if data['comments']:
                out.append("Comments found:")
                out.extend(f"  {c}" for c in data['comments'])
            if data['matches']:
                out.append(f"Pattern matches for '{self.pattern}':")
                out.extend(f"  {m}" for m in data['matches'])
            out.append("")

            if self.links:
                all_internal.update(data.get('internal_links', []))
                all_external.update(data.get('external_links', []))

        if self.links:
            out.append("=== Internal links (same domain) ===")
            for l in sorted(all_internal):
                out.append(f"  {l}")

            out.append("")
            out.append("=== External links (other domains) ===")
            for l in sorted(all_external):
                out.append(f"  {l}")

        report = "\n".join(out)

        if self.savefile:
            with open(self.savefile, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"[+] Results saved to {self.savefile}")
        else:
            print(report)


def usage():
    print(f"Usage: {sys.argv[0]} -u URL [-r] [-d DEPTH] [-c] [-w PATTERN] [-l] [-s SAVEFILE]")
    print("  -u URL       : specify the starting webpage")
    print("  -r           : recurse through links on the page (same domain only)")
    print("  -d DEPTH     : max recursion depth (requires -r, default: unlimited)")
    print("  -c           : search for comments in the HTML")
    print("  -w PATTERN   : regex pattern to search for (line-based, highlighted)")
    print("  -l           : list links (internal vs external, grouped at end)")
    print("  -s SAVEFILE  : save output to a file")
    sys.exit(1)


def main():
    args = sys.argv[1:]
    if not args or '-u' not in args:
        usage()

    url = None
    recurse = False
    pattern = None
    savefile = None
    comments = False
    links = False
    max_depth = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == '-u' and i + 1 < len(args):
            url = args[i + 1]
            i += 2
        elif arg == '-r':
            recurse = True
            i += 1
        elif arg == '-d' and i + 1 < len(args):
            try:
                max_depth = int(args[i + 1])
                if max_depth < 0:
                    raise ValueError
            except ValueError:
                print("[!] -d requires a non-negative integer")
                usage()
            i += 2
        elif arg == '-w' and i + 1 < len(args):
            pattern = args[i + 1]
            i += 2
        elif arg == '-c':
            comments = True
            i += 1
        elif arg == '-l':
            links = True
            i += 1
        elif arg == '-s' and i + 1 < len(args):
            savefile = args[i + 1]
            i += 2
        else:
            print(f"[!] Unknown argument or missing value: {arg}")
            usage()

    if not url:
        usage()

    if max_depth is not None and not recurse:
        print("[!] -d has no effect without -r")

    # Default: if no -c or -w provided, fall back to comments
    if not comments and not pattern:
        comments = True

    crawler = Crawler(base_url=url, recurse=recurse, pattern=pattern,
                      savefile=savefile, max_depth=max_depth)
    crawler.comments = comments
    crawler.links = links
    crawler.crawl(url)
    crawler.report()


if __name__ == "__main__":
    main()
