# Using ImageMagick convert:
# http://blog.room208.org/post/48793543478
# $ convert -fuzz 1% -delay 1x8 `seq -f %03g.png 10 3 72` \
#                  -coalesce -layers OptimizeTransparency animation.gif
