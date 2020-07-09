def test_outer():
    def test_inner():
        return "lol"

    lol = test_inner()
    return "wow" + lol

print(test_outer())
