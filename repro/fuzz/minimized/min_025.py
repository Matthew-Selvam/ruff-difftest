async def outer():
    await inner()
    # seen in the wild
def view():
    pass
