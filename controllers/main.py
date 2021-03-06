# -*- coding: utf-8 -*-
##############################################################################
#
#    This module uses OpenERP, Open Source Management Solution Framework.
#    Copyright (C) 2014-Today BrowseInfo (<http://www.browseinfo.in>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################


import werkzeug
from openerp import http
from openerp.http import request
from openerp import SUPERUSER_ID
from openerp.addons.website.models.website import slug
from openerp.addons.website_sale.controllers.main import QueryURL
from openerp.addons.website_sale.controllers.main import get_pricelist
from openerp.addons.web.controllers.main import login_redirect
from openerp.addons.website_sale.controllers.main import website_sale

import re
PPG = 12 # Products Per Page
PPR = 3  # Products Per Row

class table_compute(object):
    def __init__(self):
        self.table = {}

    def _check_place(self, posx, posy, sizex, sizey):
        res = True
        for y in range(sizey):
            for x in range(sizex):
                if posx+x>=PPR:
                    res = False
                    break
                row = self.table.setdefault(posy+y, {})
                if row.setdefault(posx+x) is not None:
                    res = False
                    break
            for x in range(PPR):
                self.table[posy+y].setdefault(x, None)
        return res

    def process(self, products):
        # Compute products positions on the grid
        minpos = 0
        index = 0
        maxy = 0
        for p in products:
            x = min(max(p.website_size_x, 1), PPR)
            y = min(max(p.website_size_y, 1), PPR)
            if index>=PPG:
                x = y = 1

            pos = minpos
            while not self._check_place(pos%PPR, pos/PPR, x, y):
                pos += 1
            # if 21st products (index 20) and the last line is full (PPR products in it), break
            # (pos + 1.0) / PPR is the line where the product would be inserted
            # maxy is the number of existing lines
            # + 1.0 is because pos begins at 0, thus pos 20 is actually the 21st block
            # and to force python to not round the division operation
            if index >= PPG and ((pos + 1.0) / PPR) > maxy:
                break

            if x==1 and y==1:   # simple heuristic for CPU optimization
                minpos = pos/PPR

            for y2 in range(y):
                for x2 in range(x):
                    self.table[(pos/PPR)+y2][(pos%PPR)+x2] = False
            self.table[pos/PPR][pos%PPR] = {
                'product': p, 'x':x, 'y': y,
                'class': " ".join(map(lambda x: x.html_class or '', p.website_style_ids))
            }
            if index<=PPG:
                maxy=max(maxy,y+(pos/PPR))
            index += 1

        # Format table according to HTML needs
        rows = self.table.items()
        rows.sort()
        rows = map(lambda x: x[1], rows)
        for col in range(len(rows)):
            cols = rows[col].items()
            cols.sort()
            x += len(cols)
            rows[col] = [c for c in map(lambda x: x[1], cols) if c != False]

        return rows

        # TODO keep with input type hidden


class biztech_theme(http.Controller):


    @http.route(['/home/subscribe'
    ], type='http', auth="public", website=True)
    def subscribe(self, **post):
        email=post.pop('email')
        values={'sub_error':{},'subscribe':{'email':email}}
        if not email:
            values = {'sub_error':{'email':True},'subscribe':{'email':email}}
            return request.website.render("website.homepage",values) 
        if email:
            if re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", email) != None:
                pass
            else:
                values['sub_error'].update({'email': 'invalid'})
                return request.website.render("website.homepage",values)
        cr, uid, context, pool = request.cr, request.uid, request.context, request.registry
        model_id=pool.get('ir.model').search(cr,uid,[('model','=','res.partner')])
        mass_mail = pool.get('distribution.list').search(cr,uid,[('name','=','Subscribe')])
        if not mass_mail:
            mass_mail=pool.get('distribution.list').create(cr,uid,{
                                                                   'name':'Subscribe',
                                                                   'dst_model_id': model_id[0],
                                                                   'bridge_field':'id',
                                                                   'partner_path':'id',
                                                                   'to_include_distribution_list_line_ids':[[0,False,
                                                                                                             {'name':'Subscribe',
                                                                                                              'src_model_id':model_id[0],
                                                                                                              'domain':"[['subscribe', '=', True]]"}
                                                                                                             ]]},context)
        email_id=email
        success_msg=False
        already_sub_msg=False
        if email_id:
            uid=SUPERUSER_ID
            partner=pool.get('res.partner').search(cr,uid,[('email','=',email_id),('subscribe','=',True)])
            if not partner:
                pool.get('res.partner').create(cr,uid,{'name':email_id.split('@')[0],'email':email_id,
                                                           'customer':True,'subscribe':True},context)
                success_msg='You have been subscribed successfully.'
            else:
                already_sub_msg='You are already subscribed.'         
        return request.website.render("website.homepage", {'successmsg':success_msg,'already_sub_msg':already_sub_msg})
    
    @http.route(['/home/contact_info'
    ], type='http', auth="public", website=True)    
    def contacts(self,**post):
        cr, uid, context, pool = request.cr, request.uid, request.context, request.registry
        uid=SUPERUSER_ID
        partner = pool.get('res.users').browse(cr, SUPERUSER_ID, request.uid, context).partner_id
        super_email=pool.get('res.users').browse(cr, SUPERUSER_ID, SUPERUSER_ID, context).email
        name=post.pop('full_name', '')
        email=post.pop('emp_email', '')
        subject=post.pop('email_subject', '')
        msg=post.pop('message', '')
        contact={'full_name':name,'emp_email':email,'email_subject':subject,'message':msg}
        values={'error':{},'contact':contact}  
        if not name:
            values['error'].update({'full_name': True})  
        if not email:
            values['error'].update({'emp_email': True}) 
        if email:
            if re.match("^.+\\@(\\[?)[a-zA-Z0-9\\-\\.]+\\.([a-zA-Z]{2,3}|[0-9]{1,3})(\\]?)$", email) != None:
                pass
            else:
                values['error'].update({'emp_email': 'invalid'})     
        if values and values.has_key('error')  and values['error']:
            return request.website.render("website.contactus", values)  
        if  super_email:   
            body="<p>Hello,Admin<br/><br/> Name: "+name+" <br/><br/>Email Address: "+email+ " <br/><br/> Subject: "+subject+" <br/><br/> Message:"+msg+"<br/><br/> Thanks" 
            temp_id= pool.get('ir.model.data').get_object(cr, uid, 'ecommerce_theme', 'contact_info_email')
            pool.get('email.template').write(cr, uid, temp_id.id, {'email_to': super_email,'subject' : subject,'body_html':body or ''}, context=context)
            pool.get('email.template').send_mail(cr, uid, temp_id.id,partner.id,True, context=context)                        
            return request.website.render("website.contactus", {'successmsg':'Your message has been sent successfully.'})
        return request.website.render("website.contactus", {'failmsg':'Your message has not been sent.'})
        #return request.redirect("/page/contactus")     
        
    def get_pricelist(self):
        return get_pricelist()    


    @http.route(['/shop/product/comment/<int:product_template_id>'], type='http', auth="public", methods=['GET','POST'], website=True)
    def product_comment(self, product_template_id, **post):                                          
        if not request.session.uid:            
            request.session.update({'comments':post.get('comment')})
            return login_redirect()
        cr, uid, context = request.cr, request.uid, request.context        
        if post.get('comment') or request.session.has_key('comments') and request.session.comments!=None:            
            request.registry['product.template'].message_post(
                cr, uid, product_template_id,
                body=post.get('comment') or request.session.comments,
                type='comment',
                subtype='mt_comment',
                context=dict(context, mail_create_nosubscribe=True))
            if request.session.has_key('comments') and request.session.comments!=None:
                request.session.update({'comments':None})
                return werkzeug.utils.redirect('/shop/product/' +str(product_template_id)+ "#comments")        
        return werkzeug.utils.redirect(request.httprequest.referrer + "#comments")



    @http.route(['/shop',
        '/shop/page/<int:page>',
        '/shop/category/<model("product.public.category"):category>',
        '/shop/category/<model("product.public.category"):category>/page/<int:page>'
    ], type='http', auth="public", website=True)
    def shop(self, page=0, category=None, search='', **post):
        cr, uid, context, pool = request.cr, request.uid, request.context, request.registry

        domain = request.website.sale_product_domain()
        if search:
            for srch in search.split(" "):
                domain += ['|', '|', '|', ('name', 'ilike', srch), ('description', 'ilike', srch),
                    ('description_sale', 'ilike', srch), ('product_variant_ids.default_code', 'ilike', srch)]
        if category:
            domain += [('public_categ_ids', 'child_of', int(category))]
        attrib_list = request.httprequest.args.getlist('attrib')
        attrib_values = [map(int,v.split("-")) for v in attrib_list if v]
        attrib_set = set([v[1] for v in attrib_values])

        if attrib_values:
            attrib = None
            ids = []
            for value in attrib_values:
                if not attrib:
                    attrib = value[0]
                    ids.append(value[1])
                elif value[0] == attrib:
                    ids.append(value[1])
                else:
                    domain += [('attribute_line_ids.value_ids', 'in', ids)]
                    attrib = value[0]
                    ids = [value[1]]
            if attrib:
                domain += [('attribute_line_ids.value_ids', 'in', ids)]

        keep = QueryURL('/shop', category=category and int(category), search=search, attrib=attrib_list)

        if not context.get('pricelist'):
            pricelist = self.get_pricelist()
            context['pricelist'] = int(pricelist)
        else:
            pricelist = pool.get('product.pricelist').browse(cr, uid, context['pricelist'], context)

        product_obj = pool.get('product.template')

        url = "/shop"
        product_count = product_obj.search_count(cr, uid, domain, context=context)
        if search:
            post["search"] = search
        if category:
            category = pool['product.public.category'].browse(cr, uid, int(category), context=context)
            url = "/shop/category/%s" % slug(category)
        if attrib_list:
            post['attrib'] = attrib_list
        pager = request.website.pager(url=url, total=product_count, page=page, step=PPG, scope=7, url_args=post)
        product_ids = product_obj.search(cr, uid, domain, limit=PPG, offset=pager['offset'], order='website_published desc, website_sequence desc', context=context)
        products = product_obj.browse(cr, uid, product_ids, context=context)

        style_obj = pool['product.style']
        style_ids = style_obj.search(cr, uid, [], context=context)
        styles = style_obj.browse(cr, uid, style_ids, context=context)

        category_obj = pool['product.public.category']
        category_ids = category_obj.search(cr, uid, [('parent_id', '=', False)], context=context)
        categs = category_obj.browse(cr, uid, category_ids, context=context)

        attributes_obj = request.registry['product.attribute']
        attributes_ids = attributes_obj.search(cr, uid, [], context=context)
        attributes = attributes_obj.browse(cr, uid, attributes_ids, context=context)

        from_currency = pool.get('product.price.type')._get_field_currency(cr, uid, 'list_price', context)
        to_currency = pricelist.currency_id
        compute_currency = lambda price: pool['res.currency']._compute(cr, uid, from_currency, to_currency, price, context=context)

        values = {
            'search': search,
            'category': category,
            'attrib_values': attrib_values,
            'attrib_set': attrib_set,
            'pager': pager,
            'pricelist': pricelist,
            'products': products,
            'bins': table_compute().process(products),
            'rows': PPR,
            'styles': styles,
            'categories': categs,
            'attributes': attributes,
            'compute_currency': compute_currency,
            'keep': keep,
            'style_in_product': lambda style, product: style.id in [s.id for s in product.website_style_ids],
            'attrib_encode': lambda attribs: werkzeug.url_encode([('attrib',i) for i in attribs]),
        }
        return request.website.render("website_sale.products", values)

class product_zoom_config(website_sale):
        
    @http.route(['/product/zoom_type'], type='json', auth="public", website=True)
    def get_zoom_type(self, type_id=None):
        cr, uid, context = request.cr, request.uid, request.context
        result=False
        result=request.website.inner_zoom
        return result 

    
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

