from django.test import TestCase

# Create your tests here.
import re
lnglat = re.match(r'(\d+\.?\d*),(\d+\.?\d*)', "38,125") # 38,125 / 37.5,125
if lnglat:
    print(lnglat.group(0), lnglat.group(1), lnglat(2))
else:
    print("정규표현식과 일치하지 않음")
print(lnglat)

