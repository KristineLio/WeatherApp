import wx

def pick_bg(i: int):
    # Simple rotating palette for cards
    colors = [
        wx.Colour(0, 200, 200), wx.Colour(255, 100, 150),
        wx.Colour(255, 180, 50), wx.Colour(100, 200, 255),
        wx.Colour(120, 160, 255), wx.Colour(200, 120, 255),
        wx.Colour(80, 180, 120),
    ]
    return colors[i % len(colors)]

