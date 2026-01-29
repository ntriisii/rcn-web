import hashlib

LOWER_AT = 1
UPPER_AT = 2
DIGIT_AT = 3
WORD_AT = 4
LENGTH_AT = 5  # 11-bit length to accomodate the whole URL limit
HASH_AT = LENGTH_AT + 11  # hash is 32-bit integer

UPPER = 0b0001
LOWER = 0b0010
DIGIT = 0b0100
WORD = 0b1000

DELIMITERS = ["-", "_", " ", ".", "/"]
USER_URL_COUNT = 1000


def _process_url_entity(entity):

    pattern = 0b000

    if not entity:
        return 0
    if isinstance(entity, int):
        return entity

    # check length
    pattern += len(entity) << LENGTH_AT

    # far away digits and digits spreaded across the entity
    # consecutive upper cases
    last_lower = 0
    last_upper = 0
    last_digit = 0
    consec_digits_found = 0
    consec_upper_found = 0
    digits_found = 0
    failures = 0
    count = 0
    upper_count = 0
    # entity = entity.encode('utf-8')

    # TODO: unicode chars would make the entity and entity_enc different length
    # MAYBE: unicode chars are always words or check if you can make them words
    # FIXME: check whether to use only unicode or utf-8
    while count < len(entity):
        c = ord(entity[count])
        # test for something like this
        if c >= 48 and c <= 57:
            consec_digits_found += 1 if last_digit != count - 1 else 0
            failures += 1 if last_upper == count - 1 else 0
            digits_found += 1
            last_digit = count

        elif c >= 65 and c <= 90:
            consec_upper_found += 1 if last_upper == count - 1 else 0
            last_upper = count
            upper_count += 1
        elif c >= 97 and c <= 122:
            last_lower = count

        count += 1

    # calc to check if the
    # print(consec_upper_found)
    # print(failures)
    # print(upper_count / len(entity))
    # print((upper_count < 2 and upper_count / len(entity_enc ) < 0.3))
    # FIXME: consucitve upper like vsfactTWO is not considered a word
    # FIXME: make sure to include a word like
    c = ord(entity[0])
    if (
        digits_found == len(entity)
        or (
            c > 58
            and consec_digits_found <= 1
            and failures == 0
            and consec_upper_found < 2
        )
        and not (upper_count > 2 and upper_count / len(entity) > 0.3)
        and not (len(entity) <= 3 and last_upper > 0)
    ):

        pattern += WORD
        h = (
            int.from_bytes(hashlib.sha1(entity.encode("utf-8")).digest()[:4], "little")
            << HASH_AT
        )
        pattern += h

    # MAYBE: do some avg function on the data if not a word and at least get true negatives
    # instead of false positives
    # print(entity, consec_digits_found, consec_upper_found, failures, digits_found, is_propable_word)

    pattern += LOWER if last_lower != 0 or entity[last_lower].islower() else 0b000
    pattern += UPPER if last_upper != 0 or entity[last_lower].isupper() else 0b000
    pattern += DIGIT if last_digit != 0 or entity[last_lower].isdigit() else 0b000

    return pattern


def split_entity_on_del(entity):
    entities = []
    c_word = ""
    for i in entity:
        if i in DELIMITERS:
            if c_word:
                entities.append(c_word)
            entities.append(ord(i))
            c_word = ""
            continue

        c_word += i

    entities.append(c_word)

    return entities


def make_delimited_pattern(path, delimiter: str = "/"):
    regex = []
    entities = split_entity_on_del(path)

    for entity in entities:
        pat = _process_url_entity(
            entity,
        )
        regex.append(pat)

    return regex


def get_regex_similairty(
    regex1,
    regex2,
    skip_digits=False,
    del_mul=2,
    score_divider=4,
):

    ln = regex1 if len(regex1) > len(regex2) else regex2
    shrt = regex1 if ln == regex2 else regex2
    len_diff = abs(len(ln) - len(shrt))
    remainder = ln[len(shrt) - 1 :]

    # if lengths are missed by atleast two / then return not similiar
    # 4 means that there is at least two /
    # NOTE: checking for parameters that are different and are not words
    if len_diff >= 4:
        return 0

    # longer paths with words in them should not be similiar
    for r in ln[len(shrt) - 1 :]:
        if r & WORD and not r & ~(DIGIT | WORD):
            return 0.0

    count = 0
    # [path-structure, content-similarity, length-compitability]
    scores = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    counters = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    delimiters_ord = [ord(i) for i in DELIMITERS]

    while count < len(shrt):
        # TODO do a forward and backwrad check on the regex1 like c1 with c2 -1 and c2 +1 etc
        c1 = regex1[count]
        c2b = regex2[count - 1] if count > 0 else regex2[count]
        c2a = regex2[count + 1] if count + 1 < len(regex2) else regex2[count]
        c2 = regex2[count]
        # tuples = ((c1, c2b), (c1,c2), (c1,c2a))
        tuples = ((c1, c2),)

        # check if the structure
        # check if both are words and check if the hash matches (hash is a deal breakers in here)
        # check for upper, lower, digit things and see if they match
        # check if the length matches
        for i, t in enumerate(tuples):
            r1 = t[0]
            r2 = t[1]
            sc = scores[i]
            cc = counters[i]

            # print(r1 & 0b111, r2 & 0b111)
            if (r1 in delimiters_ord or r2 in delimiters_ord) and r1 == r2:
                s = 3 if r1 == ord("/") else 1
                cscr = s if r1 == r2 else -s
                sc[0] += -0.2 if cscr == -1 else s
                cc[0] += 1

            # NOTE: having a word in the regex with the other regex with non-word
            # means that they both are different
            # check for one is word the other is not
            elif (
                r1 & WORD
                and r1 & WORD != r2 & WORD
                and (not r1 & DIGIT or not r2 & DIGIT)
            ):
                return 0.0

            # check for both are words with no digits
            elif (
                r1 & WORD
                and r1 & WORD == r2 & WORD
                and (not r1 & DIGIT or not r2 & DIGIT)
            ):
                if r1 >> (HASH_AT - 1) == r2 >> (HASH_AT - 1):
                    sc[3] += 1
                else:
                    return 0.0

                cc[2] += 1

            # check for digits only
            elif r1 & DIGIT and not r1 & ~DIGIT:
                sc[2] += 2 if (not r2 & DIGIT or r2 & ~DIGIT) else 0

            # at least two of those match
            elif (r1 & 0b0111 in [3, 5, 7] and r2 & 0b0111 in [3, 5, 7]) or (
                r1 & DIGIT and r2 & DIGIT
            ):  # when they both are numeric only
                sc[1] += 3 if r1 & 0b111 == r2 & 0b111 else 1
                sc[2] += (
                    2 if abs((r1 >> LENGTH_AT - 1) - (r2 >> LENGTH_AT - 1)) <= 2 else 0
                )
                cc[1] += 1

        count += 1

    count = 0
    all_scores = [list() for i in scores]
    # 1.25 is the average of -0.4 to 3
    while count < len(scores):
        score = scores[count]
        counter = counters[count]
        c_score = all_scores[count]
        strcut_ratio = (score[2] / counter[1]) if counter[1] else 1

        c_score.append(score[0] * strcut_ratio / (2 * counter[0]) if counter[0] else 0)
        c_score.append(score[2] / (del_mul * counter[1]) if counter[1] else 0)
        c_score.append(score[1] / (del_mul * counter[1]) if counter[1] else 0)
        c_score.append(score[3] / (del_mul * counter[2]) if counter[2] else 0)

        count += 1

    # only consider the sturcture if all the others seem aligned
    ## fist check how many words you have and how much score did you get from those
    max_score = max(sum(i) for i in all_scores)
    sim = round(max_score / score_divider, 2)

    return sim


def filter_urls_regexs_blog_content(regex):

    static_del = [ord("_"), ord("-"), ord(" ")]
    other_del = list(set(ord(i) for i in DELIMITERS) - set(static_del))
    in_del = False
    found_patt_count = 0
    for i in regex:
        if i in other_del:
            in_del = False
            continue
        if i in static_del:
            in_del = True
            continue
        if in_del and i & WORD:
            found_patt_count += 1

    return found_patt_count >= 3
