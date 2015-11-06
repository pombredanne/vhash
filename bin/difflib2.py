from difflib import SequenceMatcher, Match


class CustomSequenceMatcher(SequenceMatcher):
    def __init__(self, isjunk=None, a='', b='', match_function=None):
        SequenceMatcher.__init__(self, isjunk, a, b)
        if match_function is None:
            match_function = lambda x, y: x == y
        self.match_function = match_function

    def find_longest_match(self, alo, ahi, blo, bhi):
        """Find longest matching block in a[alo:ahi] and b[blo:bhi].

        If isjunk is not defined:

        Return (i,j,k) such that a[i:i+k] is equal to b[j:j+k], where
            alo <= i <= i+k <= ahi
            blo <= j <= j+k <= bhi
        and for all (i',j',k') meeting those conditions,
            k >= k'
            i <= i'
            and if i == i', j <= j'

        In other words, of all maximal matching blocks, return one that
        starts earliest in a, and of all those maximal matching blocks that
        start earliest in a, return the one that starts earliest in b.

        >>> s = SequenceMatcher(None, " abcd", "abcd abcd")
        >>> s.find_longest_match(0, 5, 0, 9)
        Match(a=0, b=4, size=5)

        If isjunk is defined, first the longest matching block is
        determined as above, but with the additional restriction that no
        junk element appears in the block.  Then that block is extended as
        far as possible by matching (only) junk elements on both sides.  So
        the resulting block never matches on junk except as identical junk
        happens to be adjacent to an "interesting" match.

        Here's the same example as before, but considering blanks to be
        junk.  That prevents " abcd" from matching the " abcd" at the tail
        end of the second sequence directly.  Instead only the "abcd" can
        match, and matches the leftmost "abcd" in the second sequence:

        >>> s = SequenceMatcher(lambda x: x==" ", " abcd", "abcd abcd")
        >>> s.find_longest_match(0, 5, 0, 9)
        Match(a=1, b=0, size=4)

        If no blocks match, return (alo, blo, 0).

        >>> s = SequenceMatcher(None, "ab", "c")
        >>> s.find_longest_match(0, 2, 0, 1)
        Match(a=0, b=0, size=0)
        """

        # CAUTION:  stripping common prefix or suffix would be incorrect.
        # E.g.,
        #    ab
        #    acab
        # Longest matching block is "ab", but if common prefix is
        # stripped, it's "a" (tied with "b").  UNIX(tm) diff does so
        # strip, so ends up claiming that ab is changed to acab by
        # inserting "ca" in the middle.  That's minimal but unintuitive:
        # "it's obvious" that someone inserted "ac" at the front.
        # Windiff ends up at the same place as diff, but by pairing up
        # the unique 'b's and then matching the first two 'a's.

        a, b, b2j, isbjunk = self.a, self.b, self.b2j, self.isbjunk
        besti, bestj, bestsize = alo, blo, 0
        # find longest junk-free match
        # during an iteration of the loop, j2len[j] = length of longest
        # junk-free match ending with a[i-1] and b[j]
        j2len = {}
        nothing = []
        for i in xrange(alo, ahi):
            # look at all instances of a[i] in b; note that because
            # b2j has no junk keys, the loop is skipped if a[i] is junk
            j2lenget = j2len.get
            newj2len = {}
            for j in b2j.get(a[i], nothing):
                # a[i] matches b[j]
                if j < blo:
                    continue
                if j >= bhi:
                    break
                k = newj2len[j] = j2lenget(j-1, 0) + 1
                if k > bestsize:
                    besti, bestj, bestsize = i-k+1, j-k+1, k
            j2len = newj2len

        # Extend the best by non-junk elements on each end.  In particular,
        # "popular" non-junk elements aren't in b2j, which greatly speeds
        # the inner loop above, but also means "the best" match so far
        # doesn't contain any junk *or* popular non-junk elements.
        while besti > alo and bestj > blo and \
              not isbjunk(b[bestj-1]) and \
              self.match_function(a[besti-1], b[bestj-1]):
            besti, bestj, bestsize = besti-1, bestj-1, bestsize+1
        while besti+bestsize < ahi and bestj+bestsize < bhi and \
              not isbjunk(b[bestj+bestsize]) and \
              self.match_function(a[besti+bestsize], b[bestj+bestsize]):
            bestsize += 1

        # Now that we have a wholly interesting match (albeit possibly
        # empty!), we may as well suck up the matching junk on each
        # side of it too.  Can't think of a good reason not to, and it
        # saves post-processing the (possibly considerable) expense of
        # figuring out what to do with it.  In the case of an empty
        # interesting match, this is clearly the right thing to do,
        # because no other kind of match is possible in the regions.
        while besti > alo and bestj > blo and \
              isbjunk(b[bestj-1]) and \
              self.match_function(a[besti-1], b[bestj-1]):
            besti, bestj, bestsize = besti-1, bestj-1, bestsize+1
        while besti+bestsize < ahi and bestj+bestsize < bhi and \
              isbjunk(b[bestj+bestsize]) and \
              self.match_function(a[besti+bestsize], b[bestj+bestsize]):
            bestsize = bestsize + 1

        return Match(besti, bestj, bestsize)
