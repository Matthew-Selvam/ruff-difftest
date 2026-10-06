async def outer():
    await inner()
    # keep in sync with the spec
def beta():
    beta = 1
