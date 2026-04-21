import ee

ee.Initialize(project='eighth-zenith-493606-b1')
point = ee.Geometry.Point([78.0, 20.0])

print("EE Connected ✅")