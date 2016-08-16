from selenium import webdriver
import selenium.webdriver.support.expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import unittest

class SendTextTest(unittest.TestCase):

    def setUp(self):
        self.browser = webdriver.Firefox()
        self.browser.implicitly_wait(10)

    def tearDown(self):
        self.browser.quit()

    def test_can_send_text(self):
        # -----------------------------------
        #
        # Alice opens her web browser and clicks the bookmark
        # for the app
        self.browser.get('http://127.0.0.1:5001/')

        # She notices the page has started loading as the title mentions
        # "abrim"
        self.assertIn('abrim', self.browser.title)

        # She checks that the page has fully loaded
        self.assertIn('</html>', self.browser.page_source)

        # She finds and fills the text area and press Sync to sync
        client_text_area = self.browser.find_element_by_name("client_text")

        self.assertTrue(client_text_area)

        client_text_area.clear()
        testing_text = "testing abrim sync"
        client_text_area.send_keys(testing_text)

        self.browser.find_element_by_name("submit").click()

        # The page loads again with the updated text and no errors
        self.browser.implicitly_wait(10)

        self.browser.refresh()
        wait = WebDriverWait(self.browser, 10)
        testin = wait.until(
          EC.presence_of_element_located((By.NAME, "client_text"))
        )

        self.assertIn('abrim', self.browser.title)

        # She waits for the HTML to finish loading
        self.assertIn('</html>', self.browser.page_source)
        self.assertIn( testing_text,
          self.browser.find_element_by_name("client_text").get_attribute('value')
        )

        #print(self.browser.page_source)

        # She then closes the browsers

if __name__ == '__main__':
    unittest.main()
