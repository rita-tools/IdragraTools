import copy


class TocItem:
    def __init__(self,key, title):
        self.subitems = []
        self.key = key
        self.title = title
        self.level = 0

    def addSubItem(self,subitem,pos=0):
        if pos==0:
            subitem.update_level(self.level)
            self.subitems.append(copy.deepcopy(subitem))
        else:
            # get last subitem (or creates a new subitem)
            if len(self.subitems)==0: self.subitems.append(TocItem('',''))
            lastSubItem = self.subitems[-1]
            lastSubItem.update_level(self.level)
            lastSubItem.addSubItem(subitem,pos-1)

    def addSubItems(self,subitemList,pos=0):
        for subitem in subitemList:
            self.addSubItem( subitem,pos)

    def update_level(self,level):
        self.level = level + 1
        for sub in self.subitems:
            sub.update_level(self.level)

    def getSubItemsTitles(self):
        res= []
        for sub in self.subitems:
            if sub.title!='':
                res.append(sub.title)

        return res

    def to_html(self, ul_class = '', li_class = '',level=0):
        currentItem = ''
        idx = '_%s'%self.level

        if self.level>level:
            if self.key and self.title:
                currentItem = '<li class="%s"><a href="#%s">%s</a></li>\n'%(li_class+idx,self.key,self.title)
            elif self.title:
                currentItem = '<li class="%s">%s</li>\n' % (li_class+idx, self.title)
            else:
                pass

        html = ''
        pre = ''
        post = ''


        if len(self.getSubItemsTitles())>0:
            pre = '<ul class="%s">\n' % (ul_class + idx)
            post = '</ul>\n'

        for subitem in self.subitems:
            html += subitem.to_html(ul_class, li_class,level)

        html = currentItem + pre + html + post
        return html

if __name__ == '__main__':
    parent = TocItem('parent','Parent')
    son1 =  TocItem('son1','Son 1')
    grandson11 = TocItem('grandson11','Grandson 11')
    grandson12 = TocItem('grandson12', 'Grandson 12')

    son1.addSubItems([grandson11,grandson12])

    son2 = TocItem('son2', 'Son 2')
    grandson21 = TocItem('grandson21', 'Grandson 21')
    son2.addSubItems([grandson21])

    son3 = TocItem('son3', 'Son 3')
    parent.addSubItems([son1,son2,son3])

    print(parent.to_html('cssulclass','cssliclass'))